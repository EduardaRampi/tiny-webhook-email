import os
import json
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, redirect

# ================= CONFIGURAÇÕES =================
CLIENT_ID = os.getenv("TINY_CLIENT_ID")
CLIENT_SECRET = os.getenv("TINY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("TINY_REDIRECT_URI")

API_BASE_URL = "https://api.tiny.com.br/public-api/v3"
TOKEN_URL = "https://accounts.tiny.com.br/realms/tiny/protocol/openid-connect/token"
AUTH_URL = "https://accounts.tiny.com.br/realms/tiny/protocol/openid-connect/auth"

# --- CONFIGURAÇÃO GMAIL (VENCEDORA) ---
GMAIL_REMETENTE = os.getenv("GMAIL_REMETENTE")
GMAIL_SENHA = os.getenv("GMAIL_SENHA")

app = Flask(__name__)
TOKEN_FILE = 'tokens.json'

# ================= AUXILIARES =================

def get_valid_token():
    if not os.path.exists(TOKEN_FILE): return None
    with open(TOKEN_FILE, 'r') as f: tokens = json.load(f)
    
    if time.time() > tokens['expires_at'] - 300:
        payload = {'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'refresh_token': tokens['refresh_token']}
        resp = requests.post(TOKEN_URL, data=payload)
        if resp.status_code == 200:
            tokens = resp.json()
            tokens['expires_at'] = time.time() + tokens.get('expires_in', 14400)
            with open(TOKEN_FILE, 'w') as f: json.dump(tokens, f)
            return tokens['access_token']
        return None
    return tokens['access_token']

def enviar_email(email_destino, assunto, html_corpo):
    msg = MIMEMultipart()
    msg['From'] = f"Empresa XXXX <{GMAIL_REMETENTE}>"
    msg['To'] = email_destino
    msg['Subject'] = assunto
    msg.attach(MIMEText(html_corpo, 'html'))

    try:
        # Usando a porta 465 (SSL) que funcionou no teste
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_REMETENTE, GMAIL_SENHA)
            server.sendmail(GMAIL_REMETENTE, email_destino, msg.as_string())
        print(f"✅ E-mail enviado com sucesso para {email_destino}!")
    except Exception as e:
        print(f"❌ Erro no envio de e-mail: {e}")

# ================= LÓGICA DE NEGÓCIO =================

def processar_webhook(tipo, dados_tiny):
    token = get_valid_token()
    if not token: 
        print("❌ ERRO: Token inválido. Acesse /login novamente.")
        return
    
    headers = {'Authorization': f'Bearer {token}'}
    print(f"🔍 Processando {tipo}...")

    # LÓGICA PARA NOTA FISCAL
    if tipo == 'nota_fiscal':
        id_nota = dados_tiny.get('idNotaFiscalTiny')
        print(f"📄 Processando Nota Fiscal ID: {id_nota}")
        
        # A URL da API para notas é diferente
        res = requests.get(f"{API_BASE_URL}/notas/{id_nota}", headers=headers)
        
        if res.status_code == 200:
            info = res.json().get('data', {})
            email = info.get('cliente', {}).get('email')
            # Para notas, o link do PDF é importante
            link_danfe = dados_tiny.get('urlDanfe') 
            
            if email:
                corpo = f"<h2>Sua Nota Fiscal foi emitida!</h2><p>Pode baixar o PDF aqui: {link_danfe}</p>"
                enviar_email(email, "Nota Fiscal Emitida - Odinei Peças", corpo)

    # LÓGICA PARA PEDIDO 
    elif tipo in ['venda', 'pedido_venda', 'inclusao_pedido']:
        id_pedido = dados_tiny.get('id')
        print(f"🛒 Buscando Pedido ID: {id_pedido}")
        
        res = requests.get(f"{API_BASE_URL}/pedidos/{id_pedido}", headers=headers)
        
        if res.status_code == 200:
            resposta_completa = res.json()
            print(f"DEBUG API: {resposta_completa}") 

            info = resposta_completa.get('data', {})
            
            # Garante que 'info' seja um dicionário (trata listas ou erros)
            if isinstance(info, list) and len(info) > 0:
                info = info[0]
            elif not isinstance(info, dict):
                info = resposta_completa

            cliente = info.get('cliente', {})
            if isinstance(cliente, dict):
                email = cliente.get('email')
                nome = cliente.get('nome', 'Cliente')
                numero = info.get('numeroPedido', 'S/N')
                # Valores Financeiros
                total_pedido = info.get('valorTotalPedido', 0)
                frete = info.get('valorFrete', 0)
                desconto = info.get('valorDesconto', 0)
            
                # --- BUSCA O NOME DA FORMA DE PAGAMENTO ---
                pagamento_bloco = info.get('pagamento', {})
                forma_objeto = pagamento_bloco.get('formaRecebimento', {})
                
                # Se for um dicionário, pegamos o 'nome'. Se não, pegamos o valor da condição.
                if isinstance(forma_objeto, dict):
                    forma_pagto = forma_objeto.get('nome')
                else:
                    forma_pagto = None

                # Caso o 'nome' esteja vazio, tentamos a condição de pagamento (Ex: À Vista)
                if not forma_pagto:
                    forma_pagto = pagamento_bloco.get('condicaoPagamento', 'A combinar')
                
                if email:
                    # --- MONTAGEM DA TABELA DE PRODUTOS ---
                    linhas_itens = ""
                    itens = info.get('itens', [])
                    for i in itens:
                        # Na tua estrutura: i['produto']['descricao']
                        prod = i.get('produto', {})
                        desc = prod.get('descricao', 'Produto')
                        qtd = i.get('quantidade', 0)
                        preco = i.get('valorUnitario', 0)
                        
                        linhas_itens += f"""
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{desc}</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">{qtd}</td>
                                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">R$ {preco:.2f}</td>
                            </tr>
                        """

                    # --- BLOCO DE TOTAIS (Frete e Desconto) ---
                    bloco_financeiro = ""
                    if frete and float(frete) > 0:
                        bloco_financeiro += f"<p style='text-align: right; margin: 2px;'>Frete: R$ {frete:.2f}</p>"
                    if desconto and float(desconto) > 0:
                        bloco_financeiro += f"<p style='text-align: right; margin: 2px; color: red;'>Desconto: - R$ {desconto:.2f}</p>"

                    # --- CORPO DO E-MAIL ---
                    corpo_html = f"""
                    <html>
                    <body style="font-family: sans-serif; color: #333;">
                        <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px;">
                            <h2 style="color: #2e7d32;">Olá, {nome}!</h2>
                            <p>Confirmamos a receção do seu pedido <b>#{numero}</b> na <strong>Odinei Peças</strong>.</p>
                            
                            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                                <thead>
                                    <tr style="background-color: #f8f8f8;">
                                        <th style="padding: 8px; text-align: left;">Produto</th>
                                        <th style="padding: 8px; text-align: center;">Qtd</th>
                                        <th style="padding: 8px; text-align: right;">Preço</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {linhas_itens}
                                </tbody>
                            </table>

                            <div style="border-top: 2px solid #eee; padding-top: 10px;">
                                {bloco_financeiro}
                                <p style="text-align: right; font-size: 18px;"><strong>Total: R$ {total_pedido:.2f}</strong></p>
                            </div>

                            <p><b>Forma de Pagamento:</b> {forma_pagto}</p>
                            
                            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                            <p style="font-size: 12px; color: #777; text-align: center;">
                                Obrigado pela preferência!<br>
                                <strong>Odinei Peças</strong>
                            </p>
                        </div>
                    </body>
                    </html>
                    """
                    
                    enviar_email(email, f"Pedido Confirmado #{numero} - Odinei Peças", corpo_html)
                else:
                    print("⚠️ E-mail não encontrado no cadastro do cliente.")
            else:
                print("❌ Estrutura do cliente inválida no JSON do Tiny.")
        else:
            print(f"❌ Erro na API Tiny ({res.status_code}): {res.text}")

# ================= ROTAS =================

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. Tenta pegar como formulário (o padrão comum de webhooks simples)
    dados_recebidos = request.form.to_dict()
    
    # 2. Se vier vazio, tenta pegar como JSON bruto
    if not dados_recebidos:
        dados_recebidos = request.get_json(silent=True)
        
    # 3. Se ainda estiver vazio, tenta ler o corpo da mensagem diretamente
    if not dados_recebidos:
        try:
            corpo_bruto = request.data.decode('utf-8')
            if corpo_bruto:
                dados_recebidos = json.loads(corpo_bruto)
        except:
            pass

    # Log para a gente espiar o que o Tiny está mandando de verdade
    print(f"📥 Chegou algo do Tiny! Dados: {dados_recebidos}")

    if not dados_recebidos:
        print("⚠️ O Tiny chamou, mas não consegui extrair os dados.")
        return "OK", 200

    # Extrai o tipo e os dados
    tipo = dados_recebidos.get('tipo')
    # O Tiny costuma mandar os dados dentro da chave 'dados'
    dados = dados_recebidos.get('dados')

    if tipo and dados:
        processar_webhook(tipo, dados)
    else:
        # Caso o Tiny mande em um formato diferente (ex: tudo na raiz)
        print("🔍 Formato alternativo detectado, tentando processar raiz...")
        processar_webhook("venda", dados_recebidos)
    
    return "OK", 200

@app.route('/login')
def login():
    return redirect(f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid&response_type=code")

@app.route('/callback')
def callback():
    code = request.args.get('code')
    payload = {
        'grant_type': 'authorization_code', 
        'client_id': CLIENT_ID, 
        'client_secret': CLIENT_SECRET, 
        'redirect_uri': REDIRECT_URI, 
        'code': code
    }
    resp = requests.post(TOKEN_URL, data=payload)
    if resp.status_code == 200:
        salvar_tokens(resp.json())
        return "🔥 Login realizado com sucesso! Pode fechar esta aba e criar uma venda no Tiny."
    return f"Erro na autenticação: {resp.text}", 400

def salvar_tokens(t):
    t['expires_at'] = time.time() + t.get('expires_in', 14400)
    with open(TOKEN_FILE, 'w') as f: json.dump(t, f)

if __name__ == '__main__':
    # Rode o servidor
    app.run(debug=True, port=5000)