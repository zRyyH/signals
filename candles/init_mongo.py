from pymongo import MongoClient


def init_mongo_db(
    host="207.180.193.45",
    port=27017,
    username="signals",
    password="signals1234",
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
