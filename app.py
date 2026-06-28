from flask import Flask
from routes import init_routes

app = Flask(__name__)
app.secret_key = 'skripsi_hnbakery_super_rahasia'

# Inisialisasi rute dari routes.py
init_routes(app)

if __name__ == '__main__':
    app.run(debug=True)