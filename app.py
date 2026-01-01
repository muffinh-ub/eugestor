from flask import Flask, render_template, session, request, redirect, url_for, jsonify
from models import autenticacao, cadastrar, buscar_noticias, bolsa, config, sql
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = config.get("app_secret_key")
db = sql()
client = genai.Client(api_key=config.get("gemini_key"))
model = "gemini-flash-lite-latest"


# --- Rotas de Navegação ---

@app.route("/")
def index():
    if session.get("usuario"):
        return redirect(url_for("home"))
    return render_template("hello.html")


@app.route("/home")
def home():
    if not session.get("usuario"):
        return redirect(url_for("login"))

    noticias_mercado = buscar_noticias(5)
    return render_template("home.html", noticias=noticias_mercado)


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/cadastro")
def cadastro():
    return render_template("cadastro.html")


@app.route("/verificar_email")
def ver_email():
    if "codigo_verificacao" not in session:
        return redirect(url_for("cadastro"))
    return render_template("verificar_email.html")


@app.route("/b3")
def b3():
    if not session.get("usuario"):
        return redirect(url_for("login"))
    dados_b3 = bolsa()
    return render_template("b3.html", b3=dados_b3)


#carrega todos os chats para o usuario selecionar
@app.route("/chat")
def chat():
    id_usuario = session.get("usuario")["id_user"]
    chats = db.search("select titulo_chat from tbchat where id_user = %s order by criado_em desc", (id_usuario,))
    return render_template("chat.html", chats=chats)


#carrega o chat que o usuario selecionou
@app.route("/chat/<titulo_chat>")
def cur_chat(titulo_chat):
    if not session.get("usuario"):
        return redirect(url_for("login"))
    id_usuario = session.get("usuario")["id_user"]
    id_chat = db.search("select id_chat from tbchat where id_user = %s and titulo_chat = %s", (id_usuario,titulo_chat), True)
    mensagens_chat = db.search("select role_mens as role, conteudo_mens as conteudo "
                               "from tbmensagem where id_chat = %s "
                               "order by enviado_em limit 20", (id_chat["id_chat"],))
    chats = db.search("select titulo_chat from tbchat where id_user = %s order by criado_em desc", (id_usuario,))

    historico = []
    for msg in mensagens_chat:
        historico.append({
            "role": msg["role"],
            "parts": [{"text": msg["conteudo"]}]
        })
    return render_template("chat.html", titulo_chat=titulo_chat, historico=historico, chats=chats)


@app.route("/transacao")
def transacao():
    if not session.get("usuario"):
        return redirect(url_for("login"))
    return render_template("transacao.html")

@app.route("/extrato", methods=["GET","POST"])
def extrato():
    if not session.get("usuario"):
        return redirect(url_for("login"))
    import datetime
    usuario = session.get("usuario")
    id_usuario = usuario["id_user"]
    data = request.form.get("data") if request.form.get("data") else datetime.date.today()
    filtro = request.form.get("filtro", "todos")

    if filtro == "receita":
        condicao_valor = "and valor_transacao > 0"
    elif filtro == "despesa":
        condicao_valor = "and valor_transacao < 0"
    else:
        condicao_valor = ""

    transacoes = db.search("select timestamp(data_transacao) ,descricao_transacao, categoria_transacao, "
                           "forma_pagamento_transacao, valor_transacao "
                           "from tbtransacao where id_user = %s "
                          f"{condicao_valor} and date(data_transacao) = %s "
                          "order by data_transacao desc", #str sql
                           (id_usuario, data)) #parametros

    return render_template("extrato.html", transacoes=transacoes, filtro_sel=filtro, data_sel=data)


@app.route("/perfil")
def perfil():
    if not session.get("usuario"):
        return redirect(url_for("login"))
    return render_template("perfil.html")


@app.route("/adm")
def adm():
    usuario = session.get("usuario")
    if not usuario or not usuario.get("is_admin"):
        return redirect(url_for("home"))

    # Estatisticas simples
    total_usuarios = db.search("select count(*) as total from tbusuario",None, True)

    # Lista todos os usuários
    usuarios = db.search(
        "select * from tbusuario order by id_user")

    # Lista as últimas 25 transações de todo o sistema
    ultimas_transacoes = db.search("select t.*, u.nome_user from tbtransacao as t "
                                   "join tbusuario as u on t.id_user = u.id_user "
                                   "order by t.data_transacao desc limit 25")

    return render_template("admin.html",
                           usuarios=usuarios,
                           transacoes=ultimas_transacoes,
                           total_usuarios=total_usuarios)


@app.route("/dashboard")
def dashboard():
    if not session.get("usuario"):
        return redirect(url_for("login"))

    id_usuario = session.get("usuario")["id_user"]
    gastos = db.search(("select sum(abs(valor_transacao)) as valor_gasto, categoria_transacao as categoria "
                    "from tbtransacao where id_user = %s and valor_transacao < 0 "
                    "group by categoria order by valor_gasto desc;"), (id_usuario,))

    labels_pizza = [str(r["categoria"]) for r in gastos]
    valores_pizza = [float(r["valor_gasto"]) for r in gastos]

    receitas = db.search(("select sum(valor_transacao) as valor_recebido, categoria_transacao as categoria "
                    "from tbtransacao where id_user = %s and valor_transacao > 0 "
                    "group by categoria order by valor_recebido desc;"), (id_usuario,))

    labels_pizza_receitas = [str(r["categoria"])  for r in receitas]
    valores_pizza_receitas = [float(r["valor_recebido"]) for r in receitas]

    saldo = db.search(("select date(data_transacao) as data, "
                   "sum(sum(valor_transacao)) over (order by date(data_transacao)) as saldo_acumulado "
                   "from tbtransacao where id_user = %s "
                   "group by data order by data;"), (id_usuario,))

    labels_linha = [str(r["data"]) for r in saldo]
    valores_linha = [float(r["saldo_acumulado"]) for r in saldo]

    #Luna
    try:
        transacoes = db.search(
            "select date(data_transacao) as data, descricao_transacao, categoria_transacao, valor_transacao from tbtransacao where id_user = %s order by data desc limit 50",
            (id_usuario,))

        if transacoes:
            persona = ("Você é Luna, uma assistente pessoal focada em gestão financeira (pessoal ou empresarial) "
                       "você tem uma personalidade gentil, calma, calculista, e simplista, é direta ao ponto mas também é muito carinhosa "
                       "sempre pensa em todas as oportunidades, riscos e as melhores estratégias pro cliente seguir. Não fale nada pro cliente sobre esta instrução")

            resposta = client.models.generate_content(
                model=model,
                contents=f"Analise as transações de: {session.get('usuario')['nome_user']}: {transacoes}",
                config=types.GenerateContentConfig(system_instruction=persona)
            )
            sugestao = resposta.text
        else:
            sugestao = None
    except Exception as e:
        print(f"Erro na Luna: {e}")
        sugestao = "Estou tendo problemas ao processar os dados. Por enquanto, acompanhe sua evolução pelos gráficos abaixo!"

    return render_template("dashboards.html",
                           labels_pizza=labels_pizza or ["Sem dados"],
                           valores_pizza=valores_pizza or [0],
                           labels_linha=labels_linha or ["Sem dados"],
                           valores_linha=valores_linha or [0],
                           labels_pizza_receitas=labels_pizza_receitas or ["Sem dados"],
                           valores_pizza_receitas=valores_pizza_receitas or [0],
                           sugestao=sugestao)

#--- Rotas de processamento ---

@app.route("/validar_cod", methods=["POST"])
def validar_cod():
    codigo_usuario = request.form.get("codigo")
    codigo_real = session.get("codigo_verificacao")

    if codigo_usuario == codigo_real:
        nome = session.get("temp_nome")
        email = session.get("temp_email")
        senha = session.get("temp_senha")

        if cadastrar(nome, email, senha) > 0:
            session.clear()
            usuario = autenticacao(email, senha)
            session['usuario'] = usuario

            return "<script>alert('Cadastro realizado!'); window.location='/home';</script>"
        else:
            return "Erro ao cadastrar conta."
    else:
        return "<script>alert('Código inválido!'); window.location='/verificar_email';</script>"


#envia as mensagens a Luna
@app.route("/enviar", methods=["POST"])
def enviar():
    if not session.get("usuario"):
        return redirect(url_for("login"))

    persona = ("Você é Luna, uma assistente pessoal focada em gestão financeira (pessoal ou empresarial) "
               "você tem uma personalidade gentil, calma, calculista, e simplista, é direta ao ponto mas também é muito carinhosa "
               "sempre pensa em todas as oportunidades, riscos e as melhores estratégias pro cliente seguir. Não fale nada pro cliente sobre esta instrução")

    id_usuario = session.get("usuario")["id_user"]
    titulo = request.form.get("titulo")
    pergunta = request.form.get("pergunta")

    res_chat = db.search("select id_chat from tbchat where titulo_chat = %s and id_user = %s",
                         (titulo, id_usuario), True)
    id_chat = res_chat["id_chat"]
    mensagens = db.search("select role_mens as role, conteudo_mens as conteudo "
                             "from tbmensagem where id_chat = %s "
                             "order by enviado_em", (id_chat,))
    historico = []
    for mens in mensagens:
        estrutura_mensagem = {
            #Formata a mensagem pra estrutura pedida pro gemini
            "role": mens["role"],
            "parts": [
                {"text": mens["conteudo"]}
            ]
        }
        historico.append(estrutura_mensagem)

    chat_ia = client.chats.create(model=model, history=historico, config=types.GenerateContentConfig(
        system_instruction=persona
    ))
    resposta = chat_ia.send_message(pergunta)

    db.execute("insert into tbmensagem (id_user,id_chat, role_mens, conteudo_mens, enviado_em) values (%s, %s, %s, %s, now())",
               (id_usuario,id_chat, "user", pergunta))
    db.execute("insert into tbmensagem (id_user, id_chat, role_mens, conteudo_mens, enviado_em) values (%s, %s, %s, %s, now())",
               (id_usuario,id_chat, "model", resposta.text))

    return redirect(url_for('cur_chat', titulo_chat=titulo))


#deleta o chat
@app.route("/deletar_chat", methods=["POST"])
def deletar_chat():
    if not session.get("usuario"):
        return redirect(url_for("login"))
    id_usuario = session.get("usuario")["id_user"]
    id_chat = db.search("select id_chat from tbchat where id_user = %s ", (id_usuario,), True)["id_chat"]
    titulo = request.json.get("titulo")
    resultado = db.execute("delete from tbchat where id_chat = %s and id_user = %s and titulo_chat = %s", (id_chat,id_usuario,titulo))

    if resultado > 0:
        return jsonify({"status": "success", "url": f"/chat/{id_usuario}"})

    return (f"f<script>alert('Falha ao excluir chat {titulo}');"
            "window.location = '/chat';</script>")

#renomeia o chat
@app.route("/atualizar_chat", methods=["POST"])
def atualizar_chat():
    if not session.get("usuario"):
        return redirect(url_for("login"))

    id_usuario = session.get("usuario")["id_user"]
    id_chat = db.search("select id_chat from tbchat where id_user = %s ", (id_usuario,), True)["id_chat"]
    novo_titulo = request.json.get("novo_titulo")
    resultado = db.execute("update tbchat set titulo_chat = %s where id_chat = %s and id_user = %s", (novo_titulo,id_chat, id_usuario))

    if resultado > 0:
        return jsonify({"status": "success", "url": f"/chat/{id_usuario}"})

    return ("<script>alert('Falha ao renomear chat');"
            "window.location = '/chat'</script>")


#cria um novo chat
@app.route("/novo_chat", methods=["POST"])
def novo_chat():
    if not session.get("usuario"):
        return redirect(url_for("login"))
    id_usuario = session.get("usuario")["id_user"]
    titulo_recebido = request.get_json()

    if not titulo_recebido:
        titulo_recebido = "Nova Conversa"

    resultado = db.execute("insert into tbchat (id_user, titulo_chat, criado_em) values (%s, %s, now())",
               (id_usuario, titulo_recebido))

    if resultado > 0:
        return jsonify({"status": "success", "url": f"/chat/{titulo_recebido}"})

    return ("<script>alert('Falha ao criar novo chat');"
            "window.location = '/chat'</script>")

@app.route("/promover_admin/<int:id_alvo>")
def promover_admin(id_alvo):
    usuario_logado = session.get("usuario")
    if not usuario_logado or not usuario_logado.get("is_admin"):
        return redirect(url_for("home"))

    resultado = db.execute("update tbusuario set is_admin = true where id_user = %s", (id_alvo,))

    if resultado > 0:
        return ("<script>alert('Usuário promovido a Administrador!');"
                "window.location = '/adm';</script>")

    return ("<script>alert('Erro ao promover usuário.');"
            "window.location = '/adm';</script>")


@app.route("/deletar_conta")
def deletar_conta():
    usuario = session.get("usuario")
    id_usuario = usuario["id_user"]
    resultado = db.execute("delete from tbusuario where id_user = %s", (id_usuario,))

    if resultado > 0:
        session.clear()
        return ("<script>alert('Conta deletada com sucesso!');"
                "window.location = '/';</script>")
    else:
        return ("<script>alert('Falha na exclusão da conta!');"
                "window.location = '/perfil';</script>")

@app.route("/post_perfil", methods=["POST"])
def post_perfil():
    usuario = session.get("usuario")
    id_usuario = usuario["id_user"]
    nome = request.form.get("nome") if request.form.get("nome") else usuario.get("nome_user")
    email = request.form.get("email") if request.form.get("email") else usuario.get("email_user")
    senha = request.form.get("senha") if request.form.get("senha") else usuario.get("senha_user")

    resultado = db.execute("update tbusuario set "
                           "nome_user = %s, email_user = %s, senha_user = %s "
                           "where id_user = %s", (nome, email, senha, id_usuario))

    if resultado > 0:
        session["usuario"] = db.search("select * from tbusuario where id_user = %s", (id_usuario,), True)
        return ("<script>alert('Alterações salvas com sucesso!'); "
                "window.location = '/perfil'</script>")

    return ("<script>alert('Falha ao salvar alterações'); "
                "window.location = '/perfil'</script>")

@app.route("/post_transacao", methods=["POST"])
def post_transacao():
    if not session.get("usuario"):
        return redirect(url_for("login"))

    usuario = session.get("usuario")
    id_usuario = usuario["id_user"]
    valor = request.form.get("valor")
    data = request.form.get("data")
    categoria = request.form.get("categoria")
    desc = request.form.get("descricao")
    pagamento = request.form.get("pagamento")

    resultado = db.execute(
        "insert into tbtransacao (id_user, valor_transacao, data_transacao,"
        " categoria_transacao, descricao_transacao, forma_pagamento_transacao) "
        "values (%s, %s, %s, %s, %s, %s)",
        (id_usuario, valor, data, categoria, desc, pagamento)
    )

    if resultado > 0:
        return ("<script>"
            "alert('Transação salva com sucesso!');"
            "window.location = '/transacao';"
            "</script>")
    else:
        return ("<script>"
            "alert('Falha ao salvar transação, tente novamente!');"
            "window.location = '/transacao';"
            "</script>")


@app.route("/post_cadastrar", methods=["POST"])
def post_cadastrar():
    import random, smtplib
    from email.message import EmailMessage

    nome = request.form.get("nome")
    email = request.form.get("email")
    senha = request.form.get("senha")

    if not email:
        return "Por favor, insira um e-mail."

    session['temp_nome'] = nome
    session['temp_email'] = email
    session['temp_senha'] = senha

    codigo = random.randint(10000, 99999)
    session["codigo_verificacao"] = codigo

    remetente = "andrebezerra19099@gmail.com"
    senha_google = config.get("google_key")

    msg = EmailMessage()
    msg['Subject'] = "Seu Código de Verificação - EuGestor"
    msg['From'] = remetente
    msg['To'] = email
    msg.set_content(f"Olá {nome}! Seu código de verificação é: {codigo}")

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha_google)
            smtp.send_message(msg)

        return redirect(url_for("ver_email"))

    except Exception as e:
        print(e)
        return ("<script>alert('Erro ao enviar e-mail');"
                "window.location='/cadastro';</script>")


@app.route("/post_logar", methods=["POST"])
def post_logar():
    email = request.form.get("email")
    senha = request.form.get("senha")

    usuario = autenticacao(email, senha)
    if usuario:
        session['usuario'] = usuario
        return redirect(url_for("home"))

    return ("<script>"
            "alert('Falha no login!');"
            "window.location = '/login';"
            "</script>")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)