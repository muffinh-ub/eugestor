from werkzeug.security import generate_password_hash, check_password_hash
from .sql import sql
import requests, os

db = sql()


def cadastrar(nome, email, senha):
    senha_hash = generate_password_hash(senha)
    resultado = db.execute("insert into tbusuario (nome_user, email_user, senha_user) values "
                           "(%s, %s, %s)", (nome, email, senha_hash))
    return resultado


def autenticacao(email, senha):
    usuario = db.search("select * from tbusuario "
                        "where email_user = %s", (email,), True)

    if usuario and check_password_hash(usuario["senha_user"], senha):
        return usuario
    return None


def buscar_noticias(limite=10):
    try:
        # Pega a chave 'api_news' do seu config
        api_key = os.getenv("api_news")
        url = f"https://api.marketaux.com/v1/news/all?api_token={api_key}&countries=br&language=pt&limit={limite}"

        resposta = requests.get(url)
        dados = resposta.json()
        return dados.get("data", [])

    except Exception as erro:
        print(f"Erro ao obter noticias: {erro}")
        return []


def bolsa():
    try:
        api_key = os.getenv("api_bolsa")
        url = f"https://brapi.dev/api/quote/list?token={api_key}"

        resposta = requests.get(url)
        dados = resposta.json()
        stocks = dados.get("stocks", [])

        for acao in stocks:
            ticker = acao.get("stock")
            acao["logo"] = f"https://s3-sa-east-1.amazonaws.com/bsm-logos/logos/{ticker}.png"

        return stocks

    except Exception as erro:
        print(f"Erro ao obter dados: {erro}")
        return []

def atualizar_senha(email, senha):
    senha_hash = generate_password_hash(senha)
    resultado = db.execute("update tbusuario "
                           "set senha_user = %s where email_user = %s", (senha_hash, email))
    return resultado