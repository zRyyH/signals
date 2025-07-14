from pymongo import MongoClient


def init_mongo_db(
    host="147.93.7.253",
    port=27017,
    username="mongodb",
    password="3ReSGpsD6TFDF5ww",
    target_db="candles",
):
    if username and password:
        uri = f"mongodb://{username}:{password}@{host}:{port}"
    else:
        uri = f"mongodb://{host}:{port}/"

    client = MongoClient(uri)

    db = client[target_db]

    print(f"Banco '{target_db}' inicializado com sucesso.")
    return db
