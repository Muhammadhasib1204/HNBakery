import os
from flask import Flask
from routes import init_routes

app = Flask(__name__)
app.secret_key = 'skripsi_hnbakery_super_rahasia'

init_routes(app)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )