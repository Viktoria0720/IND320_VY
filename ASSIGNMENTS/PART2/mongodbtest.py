
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://viyav0720_db_user:4ItJ6N2hraa9gnhV@ind320vy.mhrvqv5.mongodb.net/?retryWrites=true&w=majority&appName=IND320VY"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

