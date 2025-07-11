from pymongo import MongoClient


def init_mongo_db(
    host="207.180.193.45",
    port=27017,
    username="signals",
    password="signals1234",
    target_db="candles",
):
    # Monta a URI com ou sem autenticação
    if username and password:
        uri = f"mongodb://{username}:{password}@{host}:{port}"
    else:
        uri = f"mongodb://{host}:{port}/"

    # Conecta
    client = MongoClient(uri)

    # Cria o banco (Mongo cria ao inserir dados)
    db = client[target_db]

    print(f"Banco '{target_db}' inicializado com sucesso.")
    return db
