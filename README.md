# Ottawa Garbage

An Alexa skill for people living in Ottawa to find out when the next garbage day will be.

# Configuration

You need to create a .env file in the parent directory from where the garbage.py file resides.

```
database_user = 'YOUR_DATABASE_USER'
database_password = 'YOUR_DATABASE_PASSWORD'
database_name = 'garbage'
database_host = 127.0.0.1

application_id = 'YOUR_AMAZON_APPLICATION_ID'

google_maps_api_key = 'YOUR_GOOLE_MAPS_API_KEY'

verify_requests = True
```

# Building

It is currently require that you use a fork of flask-ask to run the alexa skill.  This version of flask-ask includes some support for Alexa dialog that was added recently.

```
git checkout https://github.com/stevemulligan/flask-ask
cd flask-ask
python setup.py install
```
# Server

I use gunicorn to host the application.

```
gunicorn garbage:app
```

Nginx to server everything.

```
server {
        error_log /var/log/nginx/ottawagarbage.log warn;
	listen 80;

        port_in_redirect off;

	root /var/www/ottawagarbage/root;

	server_name ottawagarbage.nonlocal.ca;

        location /garbage {
          rewrite /garbage(.*) /$1  break;
          proxy_pass http://127.0.0.1:8000;
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection 'upgrade';
          proxy_set_header Host $host;
          proxy_cache_bypass $http_upgrade;
        }
}

server {
	error_log /var/log/nginx/ottawagarbage.log warn;
        listen 80;
	root /var/www/ottawagarbage/root;
	server_name ottawagarbage-media.nonlocal.ca;
}
```
