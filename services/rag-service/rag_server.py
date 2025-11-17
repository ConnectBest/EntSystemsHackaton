import os
import re
import json
import logging
import time
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import cohere
from openai import OpenAI
from pymongo import MongoClient
from pypdf import PdfReader
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import faiss

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "tier0_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "tier0user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "tier0pass")
MONGODB_HOST = os.getenv("MONGODB_HOST", "mongodb")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_USER = os.getenv("MONGODB_USER", "tier0admin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "tier0mongo")

LOG_DIR = Path("/app/logs")
BP_DOCS_DIR = Path("/app/bp_docs")
CACHE_DIR = Path("/app/cache")  # Persist embeddings across restarts

app = FastAPI(title="RAG Service for Log Analysis")

class QueryRequest(BaseModel):
    question: str
    context: Optional[str] = None

class RAGService:
    def __init__(self):
        self.cohere_client = None
        self.openai_client = None
        self.postgres_conn = None
        self.mongo_client = None
        self.bp_documents = {}
        self.log_cache = []

        # AI provider selection (prefer OpenAI if available)
        self.use_openai = False
        self.ai_provider = None

        # Vector search components
        self.bp_chunks = []  # Store all chunks with metadata
        self.bp_embeddings = []  # Store embeddings as numpy array
        self.faiss_index = None  # FAISS index for fast similarity search
        self.embedding_dimension = 3072  # OpenAI text-embedding-3-large dimension (falls back to 1024 for Cohere)

    def connect(self):
        """Connect to services"""
        try:
            # Connect to PostgreSQL
            logger.info("Connecting to PostgreSQL...")
            self.postgres_conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
            logger.info("✓ PostgreSQL connected")

            # Connect to MongoDB
            logger.info("Connecting to MongoDB...")
            mongo_url = f"mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/"
            self.mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
            self.mongo_client.admin.command('ping')
            logger.info("✓ MongoDB connected")

            # Initialize AI providers (prefer OpenAI, fallback to Cohere)
            if OPENAI_API_KEY:
                try:
                    logger.info("Initializing OpenAI client...")
                    self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
                    self.use_openai = True
                    self.ai_provider = "OpenAI"
                    self.embedding_dimension = 3072  # text-embedding-3-large
                    logger.info("✓ OpenAI client initialized (text-embedding-3-large + gpt-4o)")
                except Exception as e:
                    logger.warning(f"OpenAI initialization failed: {e}, falling back to Cohere")
                    self.openai_client = None
                    # Fall through to Cohere initialization

            if (not self.openai_client or not OPENAI_API_KEY) and COHERE_API_KEY:
                logger.info("Initializing Cohere client...")
                self.cohere_client = cohere.Client(COHERE_API_KEY)
                self.use_openai = False
                self.ai_provider = "Cohere"
                self.embedding_dimension = 1024  # embed-english-v3.0
                logger.info("✓ Cohere client initialized (embed-english-v3.0 + command-a-vision)")
            elif not self.openai_client:
                logger.warning("⚠ No AI API keys set (OPENAI_API_KEY or COHERE_API_KEY), using rule-based responses")

            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def load_bp_documents(self):
        """Load BP annual reports"""
        logger.info("Loading BP documents...")

        if not BP_DOCS_DIR.exists():
            logger.warning(f"BP documents directory {BP_DOCS_DIR} does not exist")
            return

        for pdf_file in BP_DOCS_DIR.glob("*.pdf"):
            try:
                logger.info(f"Loading {pdf_file.name}...")

                # Try to read PDF with encryption handling
                try:
                    reader = PdfReader(str(pdf_file))

                    # Check if PDF is encrypted
                    if reader.is_encrypted:
                        logger.warning(f"{pdf_file.name} is encrypted, attempting to decrypt...")
                        # Try to decrypt with empty password (common for read-only protection)
                        reader.decrypt('')

                except Exception as decrypt_error:
                    logger.warning(f"Cannot decrypt {pdf_file.name}: {decrypt_error}, skipping...")
                    continue

                text_content = []
                for page in reader.pages:
                    try:
                        text_content.append(page.extract_text())
                    except Exception as page_error:
                        logger.warning(f"Error extracting text from page in {pdf_file.name}: {page_error}")
                        continue

                full_text = "\n".join(text_content)

                if full_text.strip():  # Only store if we got some text
                    self.bp_documents[pdf_file.stem] = {
                        "filename": pdf_file.name,
                        "text": full_text,
                        "pages": len(reader.pages),
                        "year": self._extract_year(pdf_file.name)
                    }

                    logger.info(f"  Loaded {len(reader.pages)} pages")
                else:
                    logger.warning(f"No text extracted from {pdf_file.name}")

            except Exception as e:
                logger.error(f"Error loading {pdf_file.name}: {e}, skipping...")

        logger.info(f"✓ Loaded {len(self.bp_documents)} BP documents")

    def _extract_year(self, filename: str) -> Optional[int]:
        """Extract year from filename"""
        match = re.search(r'20\d{2}', filename)
        return int(match.group()) if match else None

    def _generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding using OpenAI or Cohere with rate limiting"""
        if self.use_openai and self.openai_client:
            try:
                response = self.openai_client.embeddings.create(
                    input=text,
                    model="text-embedding-3-large"
                )
                # OpenAI paid tier: ~500 RPM, no need to sleep
                return np.array(response.data[0].embedding, dtype=np.float32)
            except Exception as e:
                logger.error(f"Error generating OpenAI embedding: {e}")
                return None
        elif self.cohere_client:
            try:
                response = self.cohere_client.embed(
                    texts=[text],
                    model="embed-english-v3.0",
                    input_type="search_document"
                )
                # Rate limiting: Trial keys allow 100 calls/min
                # Sleep 0.7s between calls = ~85 calls/min (safe buffer)
                time.sleep(0.7)
                return np.array(response.embeddings[0], dtype=np.float32)
            except Exception as e:
                logger.error(f"Error generating Cohere embedding: {e}")
                return None
        else:
            return None

    def build_vector_index(self):
        """Build FAISS vector index from BP documents"""
        if not self.openai_client and not self.cohere_client:
            logger.warning("⚠ No AI client available, skipping vector index build")
            return

        if not self.bp_documents:
            logger.warning("⚠ No BP documents loaded, skipping vector index build")
            return

        logger.info("Building vector index for BP documents...")

        all_chunks = []
        all_embeddings = []

        # Calculate total chunks first for progress estimation
        total_chunks = 0
        for doc_id, doc in self.bp_documents.items():
            chunks = self._create_overlapping_chunks(doc["text"], chunk_size=1500, overlap=300)
            total_chunks += len(chunks)

        logger.info(f"Total chunks to embed: {total_chunks}")
        if self.use_openai:
            estimated_time = (total_chunks * 0.12) / 60  # OpenAI: ~500 RPM = 0.12s per call
            logger.info(f"Estimated time: {estimated_time:.1f} minutes (OpenAI text-embedding-3-large)")
        else:
            estimated_time = (total_chunks * 0.7) / 60  # Cohere Trial: ~85 RPM = 0.7s per call
            logger.info(f"Estimated time: {estimated_time:.1f} minutes (Cohere Trial - rate limited)")

        processed_count = 0
        start_time = time.time()

        for doc_id, doc in self.bp_documents.items():
            # Create overlapping chunks
            chunks = self._create_overlapping_chunks(doc["text"], chunk_size=1500, overlap=300)

            logger.info(f"  Processing {len(chunks)} chunks from {doc['filename']}...")

            for i, chunk_text in enumerate(chunks):
                # Generate embedding
                embedding = self._generate_embedding(chunk_text)

                if embedding is not None:
                    all_chunks.append({
                        "text": chunk_text,
                        "source": doc["filename"],
                        "year": doc["year"],
                        "chunk_id": f"{doc_id}_chunk_{i}"
                    })
                    all_embeddings.append(embedding)

                processed_count += 1

                # Progress logging with time estimate
                if processed_count % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = processed_count / elapsed if elapsed > 0 else 0
                    remaining = (total_chunks - processed_count) / rate if rate > 0 else 0
                    logger.info(f"    Embedded {processed_count}/{total_chunks} chunks... "
                              f"({(processed_count/total_chunks)*100:.1f}% - ETA: {remaining/60:.1f} min)")

        if all_embeddings:
            # Convert to numpy array
            embeddings_matrix = np.vstack(all_embeddings).astype('float32')

            # Build FAISS index
            self.faiss_index = faiss.IndexFlatIP(self.embedding_dimension)  # Inner product (cosine similarity)

            # Normalize embeddings for cosine similarity
            faiss.normalize_L2(embeddings_matrix)

            # Add to index
            self.faiss_index.add(embeddings_matrix)

            # Store chunks and embeddings
            self.bp_chunks = all_chunks
            self.bp_embeddings = embeddings_matrix

            total_time = time.time() - start_time
            logger.info(f"✓ Built vector index with {len(all_chunks)} chunks in {total_time/60:.1f} minutes")
            logger.info(f"  Index size: {self.faiss_index.ntotal} vectors")

            # Save index to disk for future restarts
            self._save_vector_index()
        else:
            logger.warning("⚠ No embeddings generated, vector search will not be available")

    def _save_vector_index(self):
        """Save FAISS index and chunks to disk"""
        try:
            # Create cache directory if it doesn't exist
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Save FAISS index
            index_path = CACHE_DIR / "faiss_index.bin"
            faiss.write_index(self.faiss_index, str(index_path))

            # Save chunks metadata
            chunks_path = CACHE_DIR / "chunks.pkl"
            with open(chunks_path, 'wb') as f:
                pickle.dump(self.bp_chunks, f)

            logger.info(f"✓ Saved vector index to {CACHE_DIR}")
        except Exception as e:
            logger.error(f"Error saving vector index: {e}")

    def _load_vector_index(self) -> bool:
        """Load FAISS index and chunks from disk if available"""
        try:
            index_path = CACHE_DIR / "faiss_index.bin"
            chunks_path = CACHE_DIR / "chunks.pkl"

            # Check if cache exists
            if not index_path.exists() or not chunks_path.exists():
                logger.info("No cached vector index found")
                return False

            # Load FAISS index
            self.faiss_index = faiss.read_index(str(index_path))

            # Load chunks metadata
            with open(chunks_path, 'rb') as f:
                self.bp_chunks = pickle.load(f)

            logger.info(f"✓ Loaded cached vector index with {len(self.bp_chunks)} chunks")
            logger.info(f"  Index size: {self.faiss_index.ntotal} vectors")
            return True
        except Exception as e:
            logger.error(f"Error loading cached vector index: {e}")
            return False

    def vector_search(self, question: str, top_k: int = 5) -> List[Dict]:
        """Perform semantic search using vector similarity"""
        if (not self.openai_client and not self.cohere_client) or self.faiss_index is None:
            return []

        try:
            # Generate query embedding
            if self.use_openai and self.openai_client:
                query_response = self.openai_client.embeddings.create(
                    input=question,
                    model="text-embedding-3-large"
                )
                query_embedding = np.array(query_response.data[0].embedding, dtype=np.float32).reshape(1, -1)
            elif self.cohere_client:
                query_response = self.cohere_client.embed(
                    texts=[question],
                    model="embed-english-v3.0",
                    input_type="search_query"
                )
                query_embedding = np.array(query_response.embeddings[0], dtype=np.float32).reshape(1, -1)
            else:
                return []

            # Normalize for cosine similarity
            faiss.normalize_L2(query_embedding)

            # Search
            distances, indices = self.faiss_index.search(query_embedding, top_k)

            # Retrieve matching chunks
            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < len(self.bp_chunks):
                    chunk = self.bp_chunks[idx].copy()
                    chunk["similarity_score"] = float(distance)
                    chunk["rank"] = i + 1
                    results.append(chunk)

            logger.info(f"Vector search found {len(results)} results with scores: {[r['similarity_score'] for r in results]}")

            return results

        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    def load_system_logs(self):
        """Load and parse system logs"""
        logger.info("Loading system logs...")

        if not LOG_DIR.exists():
            logger.warning(f"Log directory {LOG_DIR} does not exist")
            return

        MAX_LINES_TO_PROCESS = 10000  # Limit to prevent memory issues

        for log_file in LOG_DIR.glob("*.log"):
            try:
                logger.info(f"Loading {log_file.name}...")
                line_count = 0
                processed_count = 0

                # Read file line-by-line instead of loading all at once
                with open(log_file, 'r') as f:
                    for line in f:
                        line_count += 1

                        # Only process first MAX_LINES_TO_PROCESS lines
                        if processed_count >= MAX_LINES_TO_PROCESS:
                            logger.info(f"  Reached limit of {MAX_LINES_TO_PROCESS} lines, skipping remaining...")
                            break

                        parsed = self._parse_log_line(line)
                        if parsed:
                            self.log_cache.append(parsed)
                            processed_count += 1

                        # Progress logging every 1000 lines
                        if line_count % 1000 == 0:
                            logger.info(f"  Processed {line_count} lines, parsed {processed_count} entries...")

                logger.info(f"  Loaded {processed_count} log entries from {line_count} total lines")

            except Exception as e:
                logger.error(f"Error loading {log_file}: {e}", exc_info=True)

        logger.info(f"✓ Loaded {len(self.log_cache)} log entries")

        # Store in PostgreSQL
        try:
            self._store_logs_in_db()
        except Exception as e:
            logger.error(f"Error storing logs in database: {e}", exc_info=True)

    def _parse_log_line(self, line: str) -> Optional[Dict]:
        """Parse Apache-style log line"""
        # Pattern: IP - - [timestamp] "METHOD /path HTTP/1.0" STATUS SIZE "REFERER" "USER_AGENT" RESPONSE_TIME
        pattern = r'(\S+) - - \[([^\]]+)\] "(\S+) (\S+) \S+" (\d+) (\d+) "([^"]*)" "([^"]*)" (\d+)'
        match = re.match(pattern, line)

        if match:
            return {
                "ip_address": match.group(1),
                "timestamp": match.group(2),
                "method": match.group(3),
                "endpoint": match.group(4),
                "status_code": int(match.group(5)),
                "response_size": int(match.group(6)),
                "referer": match.group(7) if match.group(7) != '-' else None,
                "user_agent": match.group(8),
                "response_time": int(match.group(9))
            }
        return None

    def _store_logs_in_db(self):
        """Store parsed logs in PostgreSQL"""
        if not self.log_cache:
            logger.info("No logs to store in database")
            return

        try:
            cur = self.postgres_conn.cursor()
            stored_count = 0
            error_count = 0

            # Store first 1000 for demo
            logs_to_store = self.log_cache[:1000]
            logger.info(f"Storing {len(logs_to_store)} log entries in database...")

            for log_entry in logs_to_store:
                try:
                    # Parse timestamp
                    timestamp = datetime.strptime(log_entry["timestamp"], "%d/%b/%Y:%H:%M:%S %z")

                    cur.execute("""
                        INSERT INTO system_logs
                        (ip_address, timestamp, method, endpoint, status_code, response_size, user_agent, response_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (
                        log_entry["ip_address"],
                        timestamp,
                        log_entry["method"],
                        log_entry["endpoint"],
                        log_entry["status_code"],
                        log_entry["response_size"],
                        log_entry["user_agent"],
                        log_entry["response_time"]
                    ))
                    stored_count += 1

                except Exception as entry_error:
                    error_count += 1
                    if error_count <= 5:  # Only log first 5 errors to avoid spam
                        logger.warning(f"Error storing log entry: {entry_error}, entry: {log_entry}")

            self.postgres_conn.commit()
            cur.close()
            logger.info(f"✓ Stored {stored_count} logs in database ({error_count} errors)")

        except Exception as e:
            logger.error(f"Error storing logs: {e}", exc_info=True)
            self.postgres_conn.rollback()

    def _synthesize_answer(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Synthesize answer using OpenAI or Cohere LLM"""
        if self.use_openai and self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that provides accurate, factual answers based on the provided context."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Error with OpenAI synthesis: {e}")
                return None
        elif self.cohere_client:
            try:
                response = self.cohere_client.chat(
                    message=prompt,
                    model="command-a-vision-07-2025",
                    temperature=0.3,
                    max_tokens=max_tokens
                )
                return response.text
            except Exception as e:
                logger.error(f"Error with Cohere synthesis: {e}")
                return None
        else:
            return None

    def intelligent_route_query(self, question: str) -> Dict:
        """Use AI function calling to intelligently route queries to appropriate data sources"""

        # Define available tools/functions
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_images",
                    "description": "Search site camera images for safety compliance analysis. Use this for queries about workers, safety equipment (hard hats, vests, tablets), PPE compliance, or visual site inspections. Returns image analysis with compliance scores.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The question to search image data for"
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_documents",
                    "description": "Search BP Annual Reports using semantic vector search. Use this for queries about BP operations, safety incidents, Tier 1/Tier 2 events, oil spills, annual statistics, drilling procedures, or company policies. Returns document excerpts with citations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The question to search BP documents for"
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_logs",
                    "description": "Search system operational logs in PostgreSQL. Use this for queries about IP addresses, HTTP errors, request statistics, response times, or system performance metrics. Returns log analysis and statistics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The question to search system logs for"
                            }
                        },
                        "required": ["question"]
                    }
                }
            }
        ]

        # Use OpenAI function calling
        if self.use_openai and self.openai_client:
            try:
                logger.info(f"Using OpenAI function calling to route query: {question}")

                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an intelligent query router for a Tier-0 enterprise system. Analyze the user's question and determine which data source(s) to search. You can call multiple functions if the question requires data from multiple sources."
                        },
                        {
                            "role": "user",
                            "content": question
                        }
                    ],
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.1
                )

                message = response.choices[0].message

                # Check if AI wants to call functions
                if message.tool_calls:
                    logger.info(f"AI selected {len(message.tool_calls)} tool(s): {[tc.function.name for tc in message.tool_calls]}")

                    results = []

                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        logger.info(f"Executing {function_name} with args: {function_args}")

                        # Route to appropriate function
                        if function_name == "search_images":
                            result = self.query_images(function_args["question"])
                            result["tool_used"] = "search_images"
                            results.append(result)
                        elif function_name == "search_documents":
                            result = self.query_bp_documents(function_args["question"])
                            result["tool_used"] = "search_documents"
                            results.append(result)
                        elif function_name == "search_logs":
                            result = self.query_logs(function_args["question"])
                            result["tool_used"] = "search_logs"
                            results.append(result)

                    # Combine results if multiple tools were called
                    if len(results) == 1:
                        return {
                            **results[0],
                            "routing_method": "ai_function_calling",
                            "tools_called": [results[0]["tool_used"]]
                        }
                    else:
                        # Multiple tools - synthesize combined answer
                        combined_context = []
                        tools_called = []

                        for result in results:
                            tools_called.append(result["tool_used"])
                            combined_context.append(f"From {result['tool_used']}: {result.get('answer', 'No data')}")

                        synthesis_prompt = f"""The user asked: "{question}"

Data from multiple sources:
{chr(10).join(combined_context)}

Synthesize a comprehensive answer that combines insights from all sources. Be concise but complete."""

                        synthesized_answer = self._synthesize_answer(synthesis_prompt, max_tokens=600)

                        return {
                            "answer": synthesized_answer or "\n\n".join(combined_context),
                            "sources": results,
                            "type": "multi_source_ai_routing",
                            "routing_method": "ai_function_calling",
                            "tools_called": tools_called,
                            "synthesized": True
                        }

                # No function calls - AI responded directly (shouldn't happen with tool_choice="auto")
                logger.warning("AI did not call any functions, falling back to keyword routing")
                return None

            except Exception as e:
                logger.error(f"Error with OpenAI function calling: {e}", exc_info=True)
                return None

        # Cohere tool use (similar approach)
        elif self.cohere_client:
            try:
                logger.info(f"Using Cohere tool use to route query: {question}")

                # Cohere tools format
                cohere_tools = [
                    {
                        "name": "search_images",
                        "description": "Search site camera images for safety compliance analysis. Use this for queries about workers, safety equipment (hard hats, vests, tablets), PPE compliance, or visual site inspections.",
                        "parameter_definitions": {
                            "question": {
                                "description": "The question to search image data for",
                                "type": "str",
                                "required": True
                            }
                        }
                    },
                    {
                        "name": "search_documents",
                        "description": "Search BP Annual Reports using semantic vector search. Use this for queries about BP operations, safety incidents, Tier 1/Tier 2 events, oil spills, annual statistics, or drilling procedures.",
                        "parameter_definitions": {
                            "question": {
                                "description": "The question to search BP documents for",
                                "type": "str",
                                "required": True
                            }
                        }
                    },
                    {
                        "name": "search_logs",
                        "description": "Search system operational logs. Use this for queries about IP addresses, HTTP errors, request statistics, or system performance metrics.",
                        "parameter_definitions": {
                            "question": {
                                "description": "The question to search system logs for",
                                "type": "str",
                                "required": True
                            }
                        }
                    }
                ]

                response = self.cohere_client.chat(
                    message=question,
                    model="command-a-vision-07-2025",
                    tools=cohere_tools,
                    temperature=0.1
                )

                # Check if Cohere wants to call tools
                if response.tool_calls:
                    logger.info(f"Cohere selected {len(response.tool_calls)} tool(s): {[tc.name for tc in response.tool_calls]}")

                    results = []

                    for tool_call in response.tool_calls:
                        function_name = tool_call.name
                        function_args = tool_call.parameters

                        logger.info(f"Executing {function_name} with args: {function_args}")

                        if function_name == "search_images":
                            result = self.query_images(function_args["question"])
                            result["tool_used"] = "search_images"
                            results.append(result)
                        elif function_name == "search_documents":
                            result = self.query_bp_documents(function_args["question"])
                            result["tool_used"] = "search_documents"
                            results.append(result)
                        elif function_name == "search_logs":
                            result = self.query_logs(function_args["question"])
                            result["tool_used"] = "search_logs"
                            results.append(result)

                    # Combine results
                    if len(results) == 1:
                        return {
                            **results[0],
                            "routing_method": "ai_tool_use",
                            "tools_called": [results[0]["tool_used"]]
                        }
                    else:
                        combined_context = []
                        tools_called = []

                        for result in results:
                            tools_called.append(result["tool_used"])
                            combined_context.append(f"From {result['tool_used']}: {result.get('answer', 'No data')}")

                        synthesis_prompt = f"""The user asked: "{question}"

Data from multiple sources:
{chr(10).join(combined_context)}

Synthesize a comprehensive answer."""

                        synthesized_answer = self._synthesize_answer(synthesis_prompt, max_tokens=600)

                        return {
                            "answer": synthesized_answer or "\n\n".join(combined_context),
                            "sources": results,
                            "type": "multi_source_ai_routing",
                            "routing_method": "ai_tool_use",
                            "tools_called": tools_called,
                            "synthesized": True
                        }

                logger.warning("Cohere did not call any tools, falling back to keyword routing")
                return None

            except Exception as e:
                logger.error(f"Error with Cohere tool use: {e}", exc_info=True)
                return None

        # No AI available
        return None

    def query_logs(self, question: str) -> Dict:
        """Answer questions about system logs using Cohere-enhanced analysis"""
        question_lower = question.lower()

        # Rule-based responses for common queries
        if "ip" in question_lower and ("most" in question_lower or "top" in question_lower):
            return self._get_top_ips()

        if "error" in question_lower or "400" in question_lower or "500" in question_lower:
            return self._get_error_analysis()

        if "request" in question_lower and "count" in question_lower:
            return self._get_request_stats()

        # Use AI for general log analysis queries if available
        if self.openai_client or self.cohere_client:
            try:
                # Gather log statistics for context
                cur = self.postgres_conn.cursor(cursor_factory=RealDictCursor)

                # Get overall stats
                cur.execute("""
                    SELECT
                        COUNT(*) as total_requests,
                        COUNT(DISTINCT ip_address) as unique_ips,
                        COUNT(*) FILTER (WHERE status_code >= 400) as error_count,
                        AVG(response_time) as avg_response_time,
                        MAX(response_time) as max_response_time
                    FROM system_logs
                """)
                overall_stats = cur.fetchone()

                # Get top endpoints
                cur.execute("""
                    SELECT endpoint, COUNT(*) as count
                    FROM system_logs
                    GROUP BY endpoint
                    ORDER BY count DESC
                    LIMIT 5
                """)
                top_endpoints = cur.fetchall()

                cur.close()

                # Build context for LLM
                context = f"""System Log Statistics:
- Total requests: {overall_stats['total_requests']}
- Unique IP addresses: {overall_stats['unique_ips']}
- Error count: {overall_stats['error_count']}
- Average response time: {overall_stats['avg_response_time']:.2f}ms
- Max response time: {overall_stats['max_response_time']}ms

Top 5 Endpoints:
{chr(10).join([f"- {ep['endpoint']}: {ep['count']} requests" for ep in top_endpoints])}
"""

                prompt = f"""Based on the following system log statistics, answer this question: {question}

{context}

Provide a concise, factual analysis."""

                answer = self._synthesize_answer(prompt, max_tokens=300)

                if answer:
                    logger.info(f"{self.ai_provider} synthesized answer for log query: {question}")

                    return {
                        "answer": answer,
                        "data": overall_stats,
                        "type": "log_analysis",
                        "synthesized": True
                    }

            except Exception as e:
                logger.warning(f"AI synthesis failed for logs, falling back: {e}")

        # Fallback suggestion
        return {
            "answer": "I can help you analyze system logs. Try asking about top IPs, errors, or request statistics.",
            "type": "suggestion",
            "synthesized": False
        }

    def _get_top_ips(self) -> Dict:
        """Get IP addresses generating the most requests"""
        try:
            cur = self.postgres_conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT
                    ip_address,
                    COUNT(*) as request_count,
                    COUNT(*) FILTER (WHERE status_code >= 400) as error_count,
                    AVG(response_time) as avg_response_time
                FROM system_logs
                GROUP BY ip_address
                ORDER BY request_count DESC
                LIMIT 20
            """)
            results = cur.fetchall()
            cur.close()

            if results:
                top_ip = results[0]
                answer = f"The IP address generating the most requests is {top_ip['ip_address']} "
                answer += f"with {top_ip['request_count']} requests"
                if top_ip['error_count'] > 0:
                    answer += f", including {top_ip['error_count']} errors"
                answer += "."

                return {
                    "answer": answer,
                    "data": results,
                    "type": "top_ips"
                }

            return {"answer": "No log data available", "type": "error"}

        except Exception as e:
            logger.error(f"Error querying top IPs: {e}")
            return {"answer": f"Error: {str(e)}", "type": "error"}

    def _get_error_analysis(self) -> Dict:
        """Analyze error logs"""
        try:
            cur = self.postgres_conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT
                    status_code,
                    COUNT(*) as count,
                    ARRAY_AGG(DISTINCT ip_address) as ips
                FROM system_logs
                WHERE status_code >= 400
                GROUP BY status_code
                ORDER BY count DESC
            """)
            results = cur.fetchall()
            cur.close()

            if results:
                total_errors = sum(r['count'] for r in results)
                answer = f"Found {total_errors} total errors. "
                answer += f"Most common error: {results[0]['status_code']} "
                answer += f"({results[0]['count']} occurrences)."

                return {
                    "answer": answer,
                    "data": results,
                    "type": "error_analysis"
                }

            return {"answer": "No errors found in logs", "type": "info"}

        except Exception as e:
            logger.error(f"Error analyzing errors: {e}")
            return {"answer": f"Error: {str(e)}", "type": "error"}

    def _get_request_stats(self) -> Dict:
        """Get request statistics"""
        try:
            cur = self.postgres_conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT
                    COUNT(*) as total_requests,
                    COUNT(DISTINCT ip_address) as unique_ips,
                    AVG(response_time) as avg_response_time,
                    MAX(response_time) as max_response_time
                FROM system_logs
            """)
            stats = cur.fetchone()
            cur.close()

            if stats:
                answer = f"System has processed {stats['total_requests']} requests from "
                answer += f"{stats['unique_ips']} unique IP addresses. "
                answer += f"Average response time: {stats['avg_response_time']:.2f}ms."

                return {
                    "answer": answer,
                    "data": stats,
                    "type": "request_stats"
                }

            return {"answer": "No request data available", "type": "error"}

        except Exception as e:
            logger.error(f"Error getting request stats: {e}")
            return {"answer": f"Error: {str(e)}", "type": "error"}

    def _create_overlapping_chunks(self, text: str, chunk_size: int = 1500, overlap: int = 300) -> List[str]:
        """Create overlapping text chunks to avoid cutting context"""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start += (chunk_size - overlap)
        return chunks

    def _find_pattern_matches(self, text: str, doc_info: Dict) -> List[Dict]:
        """Find specific patterns for safety incident data with surrounding context"""
        matches = []

        # Pattern 1: "X Tier 1 and Tier 2 ... events/incidents"
        pattern1 = r'(\d+)\s+Tier\s+[12]\s+(?:and|&)\s+Tier\s+[12]\s+.*?(?:event|incident)'

        # Pattern 2: "Tier 1 and 2 ... X events"
        pattern2 = r'Tier\s+[12]\s+(?:and|&)\s+[12].*?(\d+)\s+(?:event|incident)'

        # Pattern 3: General safety metrics
        pattern3 = r'(?:reported|recorded)\s+(\d+)\s+.*?(?:safety|incident|spill|event)'

        patterns = [pattern1, pattern2, pattern3]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
                # Extract generous context around match (1000 chars before and after)
                start = max(0, match.start() - 1000)
                end = min(len(text), match.end() + 1000)
                context = text[start:end].strip()

                # Calculate relevance - pattern matches get high scores
                relevance = 20  # High base score for pattern match

                # Boost if contains multiple keywords
                context_lower = context.lower()
                if "tier 1" in context_lower and "tier 2" in context_lower:
                    relevance += 10
                if "2024" in context_lower or "2023" in context_lower:
                    relevance += 5
                if any(kw in context_lower for kw in ["process safety", "oil spill", "safety event"]):
                    relevance += 5

                matches.append({
                    "text": context,
                    "source": doc_info["filename"],
                    "year": doc_info["year"],
                    "relevance": relevance,
                    "has_numbers": True,
                    "match_type": "pattern"
                })

        return matches

    def query_bp_documents(self, question: str) -> Dict:
        """Answer questions about BP documents using hybrid RAG (vector + keyword)"""
        question_lower = question.lower()

        # HYBRID SEARCH: Combine vector search with keyword/pattern matching
        all_results = []

        # Method 1: Vector semantic search (primary method)
        vector_results = self.vector_search(question, top_k=10)
        for result in vector_results:
            result["match_type"] = "vector"
            result["relevance"] = result["similarity_score"] * 30  # Scale for comparison with keyword scores
            all_results.append(result)

        logger.info(f"Vector search returned {len(vector_results)} results")

        # Method 2: Pattern-based search (for specific metrics like "38 Tier 1 and Tier 2")
        pattern_results = []
        for doc_id, doc in self.bp_documents.items():
            pattern_matches = self._find_pattern_matches(doc["text"], doc)
            pattern_results.extend(pattern_matches)

        logger.info(f"Pattern search returned {len(pattern_results)} results")
        all_results.extend(pattern_results)

        # Method 3: Keyword search (fallback if vector search unavailable)
        if not vector_results:
            logger.info("Vector search unavailable, using keyword search")

            safety_keywords = [
                "safety", "incident", "accident", "injury", "fatality",
                "hard hat", "ppe", "personal protective equipment",
                "operations", "compliance", "violation", "hazard",
                "risk", "spill", "leak", "fire", "explosion",
                "tier 1", "tier 2", "process safety", "recordable injury"
            ]

            numerical_keywords = [
                "2024", "2023", "38", "39", "96", "100",
                "severe", "reported", "decreased", "increased"
            ]

            for doc_id, doc in self.bp_documents.items():
                text = doc["text"]
                text_lower = text.lower()

                has_safety_content = any(keyword in text_lower for keyword in safety_keywords)

                if has_safety_content:
                    chunks = self._create_overlapping_chunks(text)

                    for chunk in chunks:
                        chunk_lower = chunk.lower()

                        if len(chunk) > 50 and any(kw in chunk_lower for kw in safety_keywords):
                            relevance = sum(1 for kw in safety_keywords if kw in chunk_lower)

                            has_numbers = any(kw in chunk_lower for kw in numerical_keywords)
                            if has_numbers:
                                relevance += 5

                            if any(metric in chunk_lower for metric in ["tier 1", "tier 2", "process safety", "oil spill"]):
                                relevance += 3

                            all_results.append({
                                "text": chunk,
                                "source": doc["filename"],
                                "year": doc["year"],
                                "relevance": relevance,
                                "has_numbers": has_numbers,
                                "match_type": "keyword"
                            })

        # Combine and deduplicate results
        # Remove duplicates by checking text similarity
        unique_results = []
        seen_texts = set()

        for result in all_results:
            # Use first 100 chars as deduplication key
            text_key = result["text"][:100].strip()
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                unique_results.append(result)

        # Sort by relevance (highest first)
        unique_results.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        # Debug logging
        logger.info(f"Hybrid search found {len(unique_results)} unique results")
        if unique_results:
            logger.info(f"Top result types: {[r.get('match_type', 'unknown') for r in unique_results[:5]]}")
            logger.info(f"Top result scores: {[round(r.get('relevance', 0), 2) for r in unique_results[:5]]}")

        if unique_results:
            # Get top 5 most relevant snippets for AI synthesis
            top_snippets = unique_results[:5]

            # Use AI to synthesize answer from snippets
            if self.openai_client or self.cohere_client:
                try:
                    # Build context from top snippets with adaptive sizing
                    context_parts = []

                    for i, snippet in enumerate(top_snippets):
                        source_info = f"[{snippet['source']}"
                        if snippet['year']:
                            source_info += f" - {snippet['year']}"
                        source_info += "]"

                        snippet_text = snippet['text']

                        # Adaptive snippet sizing based on content type
                        if snippet.get('match_type') == 'pattern' or snippet.get('has_numbers'):
                            # Pattern matches and numerical data get more space
                            MAX_CHARS = 1500
                        else:
                            # Regular keyword matches get standard space
                            MAX_CHARS = 800

                        # Truncate if needed
                        if len(snippet_text) > MAX_CHARS:
                            snippet_text = snippet_text[:MAX_CHARS] + "..."

                        context_parts.append(f"{source_info}\n{snippet_text}")

                        # Debug logging for first snippet
                        if i == 0:
                            logger.info(f"Top snippet preview (first 200 chars): {snippet_text[:200]}...")

                    context = "\n\n---\n\n".join(context_parts)

                    # Log context size
                    logger.info(f"Sending {len(context)} characters to {self.ai_provider} across {len(top_snippets)} snippets")

                    # Use LLM to synthesize answer
                    prompt = f"""Based on the following excerpts from BP Annual Reports, answer this question concisely and factually: {question}

Context from BP Annual Reports:
{context}

Provide a clear, factual answer with specific numbers, dates, and metrics if available. Focus on the most relevant data."""

                    answer = self._synthesize_answer(prompt, max_tokens=500)

                    if answer:
                        logger.info(f"✓ {self.ai_provider} synthesized answer for BP query: {question}")

                        return {
                            "answer": answer,
                            "sources": unique_results[:5],
                            "type": "bp_documents",
                            "synthesized": True
                        }

                except Exception as e:
                    logger.warning(f"AI synthesis failed, falling back to keyword-based response: {e}")
                    # Fall through to keyword-based response below

            # Fallback: keyword-based answer (Tier-0 reliability)
            answer = f"Found {len(unique_results)} safety-related sections in BP Annual Reports. "

            for i, snippet in enumerate(top_snippets[:3]):
                if i == 0:
                    answer += f"From {snippet['source']}"
                    if snippet['year']:
                        answer += f" ({snippet['year']})"
                    answer += ": "

                # Show snippet text (truncated if too long)
                snippet_text = snippet["text"]
                if len(snippet_text) > 400:
                    snippet_text = snippet_text[:400] + "..."

                answer += snippet_text

                # Add separator between snippets
                if i < len(top_snippets[:3]) - 1:
                    answer += "\n\nAdditional data: "

            return {
                "answer": answer,
                "sources": unique_results[:5],
                "type": "bp_documents",
                "synthesized": False
            }

        return {
            "answer": "No relevant information found in BP documents for this query.",
            "type": "no_match",
            "synthesized": False
        }

    def query_images(self, question: str) -> Dict:
        """Query images based on safety equipment keywords with Cohere-enhanced analysis"""
        question_lower = question.lower()

        try:
            # Extract what we're looking for
            looking_for_hard_hat = any(kw in question_lower for kw in ["hard hat", "helmet", "hat"])
            looking_for_tablet = any(kw in question_lower for kw in ["tablet", "device", "ipad"])
            looking_for_vest = any(kw in question_lower for kw in ["vest", "safety vest"])
            without = "without" in question_lower

            # Query MongoDB for images
            db = self.mongo_client['tier0_images']
            collection = db['images']

            # Build query based on keywords
            query = {"processed": True}

            # Apply filters based on safety compliance
            if looking_for_hard_hat:
                if without:
                    query["safety_compliance.has_hard_hat"] = False
                else:
                    query["safety_compliance.has_hard_hat"] = True

            if looking_for_tablet:
                query["safety_compliance.has_inspection_equipment"] = True

            if looking_for_vest:
                query["safety_compliance.has_safety_vest"] = True

            # Find matching images
            results = list(collection.find(query, {
                "_id": 0,
                "filename": 1,
                "device_type": 1,
                "description": 1,
                "safety_compliance": 1,
                "keywords": 1
            }).limit(20))

            if results:
                # Group by device type (which represents sites)
                sites = {}
                for img in results:
                    device_type = img.get("device_type", "unknown")
                    if device_type not in sites:
                        sites[device_type] = []
                    sites[device_type].append(img)

                # Calculate statistics
                compliance_scores = [img.get("safety_compliance", {}).get("compliance_score", 0) for img in results]
                avg_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0

                # Use AI to synthesize analysis if available
                if self.openai_client or self.cohere_client:
                    try:
                        # Build context from image data
                        image_context = []
                        for site, images in sites.items():
                            site_compliance = [img.get("safety_compliance", {}).get("compliance_score", 0) for img in images]
                            site_avg = sum(site_compliance) / len(site_compliance) if site_compliance else 0

                            # Get common keywords for this site
                            all_keywords = []
                            for img in images:
                                all_keywords.extend(img.get("keywords", []))

                            from collections import Counter
                            common_keywords = [kw for kw, _ in Counter(all_keywords).most_common(5)]

                            image_context.append(
                                f"Site: {site}\n"
                                f"Images: {len(images)}\n"
                                f"Avg Compliance: {site_avg:.1f}%\n"
                                f"Common themes: {', '.join(common_keywords)}"
                            )

                        context = "\n\n".join(image_context)

                        prompt = f"""Based on site camera image analysis data, answer this question: {question}

Image Analysis Data:
{context}

Total images analyzed: {len(results)}
Overall average compliance: {avg_compliance:.1f}%
Sites covered: {', '.join(sites.keys())}

Provide a concise summary focusing on safety compliance trends and any concerns."""

                        answer = self._synthesize_answer(prompt, max_tokens=300)

                        if answer:
                            logger.info(f"{self.ai_provider} synthesized answer for image query: {question}")

                            return {
                                "answer": answer,
                                "data": results,
                                "sites": list(sites.keys()),
                                "count": len(results),
                                "avg_compliance": round(avg_compliance, 1),
                                "type": "image_analysis",
                                "synthesized": True
                            }

                    except Exception as e:
                        logger.warning(f"AI synthesis failed for images, falling back: {e}")
                        # Fall through to keyword-based response

                # Fallback: keyword-based answer (Tier-0 reliability)
                if without:
                    answer = f"Found {len(results)} images showing workers WITHOUT proper safety equipment. "
                else:
                    answer = f"Found {len(results)} images showing workers with proper safety equipment. "

                answer += f"Sites: {', '.join(sites.keys())}. "
                answer += f"Average safety compliance: {avg_compliance:.1f}%."

                return {
                    "answer": answer,
                    "data": results,
                    "sites": list(sites.keys()),
                    "count": len(results),
                    "avg_compliance": round(avg_compliance, 1),
                    "type": "image_analysis",
                    "synthesized": False
                }

            return {
                "answer": "No matching images found. The image processor may still be analyzing site camera feeds.",
                "type": "no_match",
                "synthesized": False
            }

        except Exception as e:
            logger.error(f"Error querying images: {e}")
            return {
                "answer": f"Error querying image database: {str(e)}",
                "type": "error",
                "synthesized": False
            }

# Initialize service
rag_service = RAGService()

@app.on_event("startup")
async def startup_event():
    """Initialize RAG service on startup"""
    logger.info("Starting RAG service...")
    try:
        if rag_service.connect():
            try:
                rag_service.load_bp_documents()

                # Try to load cached vector index first (fast)
                if rag_service._load_vector_index():
                    logger.info("Using cached vector index - startup complete!")
                else:
                    # Build vector index from scratch (slow - 30+ minutes)
                    logger.info("Building vector index from scratch...")
                    rag_service.build_vector_index()
            except Exception as e:
                logger.error(f"Error loading BP documents: {e}", exc_info=True)

            try:
                rag_service.load_system_logs()
            except Exception as e:
                logger.error(f"Error loading system logs: {e}", exc_info=True)

            logger.info("✓ RAG service ready")
        else:
            logger.error("✗ Failed to initialize RAG service connections")
    except Exception as e:
        logger.error(f"✗ Critical error during startup: {e}", exc_info=True)
        # Don't re-raise - let the service start even if initialization fails
        logger.warning("RAG service started with errors - some features may not be available")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "RAG Service"}

@app.post("/query")
async def process_query(request: QueryRequest):
    """Process natural language queries with AI-driven routing"""
    question = request.question
    question_lower = question.lower()

    # PHASE 1: Try AI-driven intelligent routing (OpenAI function calling / Cohere tool use)
    logger.info(f"Processing query: {question}")

    ai_result = rag_service.intelligent_route_query(question)

    if ai_result:
        logger.info(f"✓ AI routing succeeded. Tools called: {ai_result.get('tools_called', [])}")
        result = ai_result
    else:
        # PHASE 2: Fallback to keyword-based routing (Tier-0 reliability)
        logger.info("AI routing unavailable, using keyword-based routing (Tier-0 fallback)")

        # For safety/incident queries, combine BP documents AND images
        is_safety_query = any(keyword in question_lower for keyword in [
            "incident", "safety", "hard hat", "helmet", "vest",
            "equipment", "compliance", "without"
        ])

        if is_safety_query:
            # Query both BP documents AND images for comprehensive answer
            bp_result = rag_service.query_bp_documents(question)
            image_result = rag_service.query_images(question)

            # Combine results
            combined_answer = ""

            # Add BP document insights
            if bp_result.get("type") == "bp_documents":
                combined_answer += "According to BP Annual Reports: " + bp_result["answer"] + "\n\n"

            # Add image analysis
            if image_result.get("type") == "image_analysis":
                combined_answer += "Based on site camera analysis: " + image_result["answer"]
            elif not combined_answer:
                # If no BP data, show just image data
                combined_answer = image_result["answer"]

            result = {
                "answer": combined_answer if combined_answer else "No safety incident data available.",
                "bp_sources": bp_result.get("sources", []),
                "image_data": image_result.get("data", []),
                "sites": image_result.get("sites", []),
                "avg_compliance": image_result.get("avg_compliance"),
                "type": "combined_safety_analysis",
                "routing_method": "keyword_fallback"
            }

        # Check for image-only queries (specific sites/workers)
        elif any(keyword in question_lower for keyword in [
            "image", "camera", "site", "worker", "engineer", "tablet"
        ]):
            result = rag_service.query_images(question)
            result["routing_method"] = "keyword_fallback"

        # Check for log-related queries
        elif any(keyword in question_lower for keyword in ["log", "ip", "error", "request"]):
            result = rag_service.query_logs(question)
            result["routing_method"] = "keyword_fallback"

        # Check for BP document queries only
        elif any(keyword in question_lower for keyword in ["bp", "drill", "operation", "annual report"]):
            result = rag_service.query_bp_documents(question)
            result["routing_method"] = "keyword_fallback"

        else:
            result = {
                "answer": "Please specify if you're asking about:\n- Safety incidents/compliance (combines BP reports + site images)\n- Site camera images (workers, equipment)\n- System logs (IP addresses, errors)\n- BP operations (drilling, procedures)",
                "type": "clarification",
                "routing_method": "keyword_fallback"
            }

    return {
        "question": question,
        "result": result,
        "timestamp": datetime.utcnow().isoformat()
    }

# ============= SPECIALIZED QUERY ENDPOINTS =============

@app.post("/query/images")
async def query_images_endpoint(request: QueryRequest):
    """Explicit image search - MongoDB embeddings for safety compliance analysis

    Examples:
    - "Show workers without hard hats"
    - "Find sites with tablets"
    - "Workers with safety vests"
    """
    result = rag_service.query_images(request.question)
    return {
        "question": request.question,
        "result": result,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "mongodb_images"
    }

@app.post("/query/documents")
async def query_documents_endpoint(request: QueryRequest):
    """Explicit PDF search - Vector semantic search (FAISS) on BP Annual Reports

    Examples:
    - "BP safety incidents in 2024"
    - "Tier 1 and Tier 2 events"
    - "Oil spill statistics"
    """
    result = rag_service.query_bp_documents(request.question)
    return {
        "question": request.question,
        "result": result,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "bp_documents_vector_search"
    }

@app.post("/query/logs")
async def query_logs_endpoint(request: QueryRequest):
    """Explicit log search - PostgreSQL operational data (system_logs table)

    Examples:
    - "Top IP addresses"
    - "Error analysis"
    - "Request statistics"
    """
    result = rag_service.query_logs(request.question)
    return {
        "question": request.question,
        "result": result,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "postgresql_logs"
    }

# ============= SERVICE STATS =============

@app.get("/stats")
async def get_stats():
    """Get RAG service statistics"""
    return {
        "bp_documents_loaded": len(rag_service.bp_documents),
        "log_entries_cached": len(rag_service.log_cache),
        "cohere_enabled": rag_service.cohere_client is not None,
        "openai_enabled": rag_service.openai_client is not None,
        "ai_provider": rag_service.ai_provider,
        "vector_index_size": rag_service.faiss_index.ntotal if rag_service.faiss_index else 0,
        "endpoints": {
            "unified": "/query (auto-routes based on keywords)",
            "images": "/query/images (MongoDB image embeddings)",
            "documents": "/query/documents (FAISS vector search on PDFs)",
            "logs": "/query/logs (PostgreSQL operational logs)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
