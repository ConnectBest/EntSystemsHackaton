FROM nginx:alpine

COPY login.html /usr/share/nginx/html/
COPY dashboard.html /usr/share/nginx/html/
COPY dashboard.js /usr/share/nginx/html/
COPY index.html /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
