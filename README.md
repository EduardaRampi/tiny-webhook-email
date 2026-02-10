# tiny-webhook-email
Integração com o Tiny ERP via API e Webhooks para envio automático de e-mails ao cliente após vendas e emissão de notas fiscais..


## 📌 Sobre o projeto

Este projeto foi desenvolvido em **Python com Flask** e tem como objetivo automatizar a comunicação com clientes, enviando e-mails automaticamente sempre que:

- Uma **venda/pedido** é criado ou finalizado no Tiny
- Uma **nota fiscal** é emitida

O sistema recebe os webhooks do Tiny, consulta os dados completos via API e dispara e-mails personalizados para o cliente final.

---

## ⚙️ Funcionalidades

- Recebimento de webhooks do Tiny ERP
- Autenticação OAuth2 com Tiny
- Consulta de pedidos e notas fiscais via API
- Envio automático de e-mails HTML
- Suporte a:
  - Confirmação de pedido
  - Envio de link da DANFE (nota fiscal)

---

## 🛠️ Tecnologias utilizadas

- Python 3
- Flask
- Tiny ERP API
- Requests
- SMTP (Gmail)

---

## 🔐 Configuração

Crie um arquivo `.env` baseado no arquivo `.env.example` e preencha com suas credenciais:
TINY_CLIENT_ID=
TINY_CLIENT_SECRET=
TINY_REDIRECT_URI=

GMAIL_REMETENTE=
GMAIL_SENHA=

## 🌐 Webhooks em ambiente local

Durante o desenvolvimento, é necessário expor o servidor local para que o Tiny consiga enviar os webhooks.

Uma forma simples de fazer isso é utilizando o **ngrok**.

Exemplo:

ngrok http 5000

## ✨ Autor

Desenvolvido por Eduarda Rampi