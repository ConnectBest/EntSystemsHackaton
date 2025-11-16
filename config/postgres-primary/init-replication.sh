#\!/bin/sh
# Create replication slot for streaming replication

psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT CASE
        WHEN EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = 'replication_slot')
        THEN 'Replication slot already exists'
        ELSE pg_create_physical_replication_slot('replication_slot')::text
    END;
EOSQL

echo "Replication slot setup complete"
