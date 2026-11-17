from datetime import datetime
import html
import time
import requests
import telebot
from telebot import types

TOKEN = "9196719546:AAGD4bne4AXYpFCzdkATd31QcMBZViyMoTE"
bot = telebot.TeleBot(TOKEN)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}

LOJAS_PADRAO = {
    "1": "Steam",
    "2": "GamersGate",
    "3": "GreenManGaming",
    "7": "GOG",
    "8": "Origin / EA",
    "11": "Humble Store",
    "13": "Ubisoft Store",
    "15": "Fanatical",
    "25": "Epic Games Store",
    "27": "Gamesplanet",
    "31": "Blizzard Shop",
}

# Controle de sessão dos usuários
usuarios_iniciados = set()
aguardando_busca = set()

# Cache simples da cotação do dólar (atualiza a cada 15 min)
cache_dolar = {"valor": 5.75, "atualizado_em": 0}


def obter_cotacao_dolar():
    agora = time.time()
    if agora - cache_dolar["atualizado_em"] < 900:
        return cache_dolar["valor"]

    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL"
        resposta = requests.get(url, timeout=8).json()
        cotacao = float(resposta["USDBRL"]["bid"])
        cache_dolar["valor"] = cotacao
        cache_dolar["atualizado_em"] = agora
        return cotacao
    except Exception:
        return cache_dolar["valor"]


def formatar_brl(valor_usd, cotacao):
    valor_brl = float(valor_usd) * cotacao
    return (
        f"R$ {valor_brl:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def carregar_lojas():
    url = "https://www.cheapshark.com/api/1.0/stores"
    try:
        resposta = requests.get(url, headers=HEADERS, timeout=10).json()
        if isinstance(resposta, list):
            return {
                loja["storeID"]: loja["storeName"]
                for loja in resposta
                if isinstance(loja, dict)
            }
    except Exception:
        pass
    return LOJAS_PADRAO


lojas = carregar_lojas()


def teclado_numerado():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("1 - Procurar"),
        types.KeyboardButton("2 - Ver Melhores Ofertas"),
        types.KeyboardButton("3 - Jogos Baratinhos"),
        types.KeyboardButton("4 - Cotação do Dólar"),
        types.KeyboardButton("5 - Sair"),
    )
    return markup


def registrar_comandos():
    try:
        bot.set_my_commands([
            types.BotCommand("menu", "Abrir o menu principal numerado"),
            types.BotCommand("top", "Ver as 5 melhores ofertas do momento"),
            types.BotCommand("baratos", "Jogos em promoção por menos de US$ 3"),
            types.BotCommand("dolar", "Consultar cotação atual do dólar"),
            types.BotCommand("sair", "Encerrar atendimento"),
        ])
    except Exception:
        pass


def enviar_menu_inicial(mensagem):
    chat_id = mensagem.chat.id
    usuarios_iniciados.add(chat_id)
    aguardando_busca.discard(chat_id)

    cotacao = obter_cotacao_dolar()
    cotacao_fmt = f"R$ {cotacao:.2f}".replace(".", ",")

    texto = (
        "🎮 <b>Bem-vindo ao Caçador de Promoções de Jogos!</b>\n\n"
        "Eu pesquiso o menor preço atual de jogos nas principais lojas"
        " digitais (Steam, Epic Games, GOG, etc.) e converto tudo para"
        " <b>Reais (R$)</b> em tempo real.\n\n"
        "📌 <b>Comandos que eu atendo:</b>\n"
        "• /menu — Exibe esta tela de opções\n"
        "• /top — Lista as 5 melhores promoções de hoje\n"
        "• /baratos — Jogos por menos de US$ 3,00\n"
        "• /dolar — Mostra a cotação atual do dólar\n"
        "• /sair — Encerra a sessão\n\n"
        "👇 <b>Aperte ou digite um número para começar:</b>\n\n"
        "<b>1</b> - Procurar\n"
        "<b>2</b> - Ver Melhores Ofertas\n"
        "<b>3</b> - Jogos Baratinhos\n"
        "<b>4</b> - Cotação do Dólar\n"
        "<b>5</b> - Sair\n\n"
        f"💱 <i>Cotação base: US$ 1,00 = {cotacao_fmt}</i>"
    )
    bot.send_message(
        chat_id,
        texto,
        parse_mode="HTML",
        reply_markup=teclado_numerado(),
    )


@bot.message_handler(commands=["start", "help", "menu"])
def comando_inicio(mensagem):
    enviar_menu_inicial(mensagem)


@bot.message_handler(commands=["dolar"])
def comando_dolar(mensagem):
    usuarios_iniciados.add(mensagem.chat.id)
    cotacao = obter_cotacao_dolar()
    cotacao_fmt = f"R$ {cotacao:.2f}".replace(".", ",")
    texto = (
        "💵 <b>Cotação Comercial (USD → BRL)</b>\n\n"
        f"• <b>1 Dólar Americano:</b> {cotacao_fmt}\n"
        "• <b>Fonte:</b> AwesomeAPI (tempo real)\n\n"
        "<i>Envie <b>0</b> para voltar ao menu ou digite o nome de um jogo.</i>"
    )
    bot.reply_to(mensagem, texto, parse_mode="HTML")


@bot.message_handler(commands=["top"])
def comando_top(mensagem):
    usuarios_iniciados.add(mensagem.chat.id)
    listar_ofertas_especiais(
        mensagem,
        params={"sortBy": "DealRating", "pageSize": 5, "onSale": 1},
        titulo_lista="🔥 <b>Top 5 Melhores Ofertas do Momento</b>",
    )


@bot.message_handler(commands=["baratos"])
def comando_baratos(mensagem):
    usuarios_iniciados.add(mensagem.chat.id)
    listar_ofertas_especiais(
        mensagem,
        params={
            "upperPrice": 3,
            "sortBy": "Savings",
            "pageSize": 5,
            "onSale": 1,
        },
        titulo_lista="💸 <b>Top 5 Promoções Abaixo de US$ 3,00</b>",
    )


@bot.message_handler(commands=["sair"])
def comando_sair(mensagem):
    chat_id = mensagem.chat.id
    usuarios_iniciados.discard(chat_id)
    aguardando_busca.discard(chat_id)

    texto = (
        "👋 <b>Atendimento encerrado!</b>\n\n"
        "Obrigado por usar o Caçador de Promoções. Quando quiser começar"
        " novamente, basta enviar qualquer mensagem ou digitar /start."
    )
    bot.send_message(
        chat_id,
        texto,
        parse_mode="HTML",
        reply_markup=types.ReplyKeyboardRemove(),
    )


def listar_ofertas_especiais(mensagem, params, titulo_lista):
    bot.send_chat_action(mensagem.chat.id, "typing")
    cotacao = obter_cotacao_dolar()

    try:
        resposta = requests.get(
            "https://www.cheapshark.com/api/1.0/deals",
            params=params,
            headers=HEADERS,
            timeout=10,
        ).json()

        if not isinstance(resposta, list) or not resposta:
            bot.reply_to(
                mensagem, "Nenhuma oferta disponível nessa categoria agora."
            )
            return

        linhas = [titulo_lista, ""]
        for i, item in enumerate(resposta, start=1):
            nome = html.escape(item["title"])
            loja = html.escape(lojas.get(item["storeID"], "Loja digital"))
            preco_brl = formatar_brl(item["salePrice"], cotacao)
            preco_usd = item["salePrice"]
            desconto = round(float(item["savings"]))
            link = (
                f"https://www.cheapshark.com/redirect?dealID={item['dealID']}"
            )

            linhas.append(
                f"<b>{i}. {nome}</b>\n"
                f"   🏪 {loja} | 🏷️ <b>-{desconto}%</b>\n"
                f"   💰 <b>{preco_brl}</b> (US$ {preco_usd}) — <a"
                f" href='{link}'>Ver oferta</a>\n"
            )

        linhas.append("<i>💡 Digite <b>1</b> para buscar um jogo ou <b>0</b> para o menu.</i>")

        bot.reply_to(
            mensagem,
            "\n".join(linhas),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        bot.reply_to(
            mensagem, "Erro ao buscar a lista de ofertas. Tente novamente."
        )


@bot.message_handler(func=lambda mensagem: True)
def tratar_texto(mensagem):
    chat_id = mensagem.chat.id
    texto = mensagem.text.strip()
    texto_lower = texto.lower()

    # 1) Se for a primeira mensagem do usuário na sessão, mostra o guia e o menu
    if chat_id not in usuarios_iniciados:
        return enviar_menu_inicial(mensagem)

    # 2) Se o usuário escolheu "1 - Procurar", trata a próxima mensagem como o nome do jogo
    if chat_id in aguardando_busca:
        aguardando_busca.discard(chat_id)
        if texto_lower in ["0", "menu", "voltar"]:
            return enviar_menu_inicial(mensagem)
        if texto_lower in ["5", "5 - sair", "sair"]:
            return comando_sair(mensagem)
        return buscar_jogo(mensagem, texto)

    # 3) Tratamento das opções numeradas e botões
    if texto_lower in ["1", "1 - procurar", "procurar"]:
        aguardando_busca.add(chat_id)
        bot.reply_to(
            mensagem,
            "🔍 <b>Qual jogo você quer procurar?</b>\n"
            "Digite o nome do jogo abaixo (ex: <i>Hollow Knight</i>, <i>Elden Ring</i>):",
            parse_mode="HTML",
        )
        return

    if texto_lower in ["2", "2 - ver melhores ofertas", "melhores ofertas"]:
        return comando_top(mensagem)

    if texto_lower in ["3", "3 - jogos baratinhos", "jogos baratinhos"]:
        return comando_baratos(mensagem)

    if texto_lower in ["4", "4 - cotação do dólar", "cotação do dólar", "dolar"]:
        return comando_dolar(mensagem)

    if texto_lower in ["5", "5 - sair", "sair"]:
        return comando_sair(mensagem)

    if texto_lower in ["0", "menu", "ajuda", "voltar"]:
        return enviar_menu_inicial(mensagem)

    # 4) Se o usuário já passou da tela inicial e digitou direto o nome de um jogo
    buscar_jogo(mensagem, texto)


def buscar_jogo(mensagem, nome_jogo):
    bot.send_chat_action(mensagem.chat.id, "typing")
    cotacao = obter_cotacao_dolar()

    url = "https://www.cheapshark.com/api/1.0/deals"
    parametros = {"title": nome_jogo, "sortBy": "Price", "limit": 1}

    try:
        resposta = requests.get(
            url, params=parametros, headers=HEADERS, timeout=10
        )
        ofertas = resposta.json()

        if not isinstance(ofertas, list) or not ofertas:
            bot.reply_to(
                mensagem,
                "😕 Nenhuma oferta encontrada para"
                f" <b>{html.escape(nome_jogo)}</b>.\nTente digitar o nome"
                " original em inglês (ex: <i>The Witcher 3</i>) ou envie"
                " <b>0</b> para voltar ao menu.",
                parse_mode="HTML",
            )
            return

        melhor = ofertas[0]
        titulo = html.escape(melhor["title"])
        preco_atual_usd = melhor["salePrice"]
        preco_normal_usd = melhor["normalPrice"]
        preco_atual_brl = formatar_brl(preco_atual_usd, cotacao)
        preco_normal_brl = formatar_brl(preco_normal_usd, cotacao)

        desconto = round(float(melhor["savings"]))
        nome_loja = html.escape(lojas.get(melhor["storeID"], "Loja digital"))
        link = f"https://www.cheapshark.com/redirect?dealID={melhor['dealID']}"
        game_id = melhor.get("gameID", "")
        thumb = melhor.get("thumb", "")

        avaliacoes = []
        metacritic = melhor.get("metacriticScore", "0")
        steam_pct = melhor.get("steamRatingPercent", "0")
        if metacritic and int(metacritic) > 0:
            avaliacoes.append(f"⭐ Metacritic: <b>{metacritic}/100</b>")
        if steam_pct and int(steam_pct) > 0:
            avaliacoes.append(f"👍 Steam: <b>{steam_pct}%</b>")
        bloco_notas = (
            f"\n{' | '.join(avaliacoes)}" if avaliacoes else ""
        )

        if desconto > 0:
            bloco_preco = (
                f"💰 <b>Menor preço:</b> {preco_atual_brl} (<s>{preco_normal_brl}</s>)\n"
                f"🇺🇸 <b>Em dólar:</b> US$ {preco_atual_usd} (de US$ {preco_normal_usd})\n"
                f"🏷️ <b>Desconto:</b> <b>{desconto}% OFF</b>"
            )
        else:
            bloco_preco = (
                f"💰 <b>Preço atual:</b> {preco_atual_brl} (sem desconto no momento)\n"
                f"🇺🇸 <b>Em dólar:</b> US$ {preco_atual_usd}"
            )

        legenda = (
            f"🕹️ <b>{titulo}</b>\n"
            f"🏪 <b>Melhor loja:</b> {nome_loja}\n\n"
            f"{bloco_preco}"
            f"{bloco_notas}\n\n"
            "<i>💡 Digite outro jogo ou envie <b>0</b> para o menu.</i>"
        )

        botoes = types.InlineKeyboardMarkup(row_width=1)
        botoes.add(
            types.InlineKeyboardButton(
                f"🛒 Abrir oferta na {nome_loja}", url=link
            )
        )
        if game_id:
            botoes.add(
                types.InlineKeyboardButton(
                    "📊 Comparar Lojas e Recorde Histórico",
                    callback_data=f"detalhes_{game_id}",
                )
            )

        if thumb:
            try:
                bot.send_photo(
                    mensagem.chat.id,
                    thumb,
                    caption=legenda,
                    parse_mode="HTML",
                    reply_markup=botoes,
                )
                return
            except Exception:
                pass

        bot.send_message(
            mensagem.chat.id,
            legenda,
            parse_mode="HTML",
            reply_markup=botoes,
        )

    except Exception:
        bot.reply_to(
            mensagem,
            "⚠️ Não consegui consultar as ofertas agora. Tente novamente em"
            " instantes.",
        )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("detalhes_")
)
def callback_detalhes(call):
    game_id = call.data.split("_")[1]
    bot.answer_callback_query(call.id, "Buscando histórico e outras lojas...")
    cotacao = obter_cotacao_dolar()

    try:
        url = f"https://www.cheapshark.com/api/1.0/games?id={game_id}"
        dados = requests.get(url, headers=HEADERS, timeout=10).json()

        titulo = html.escape(dados.get("info", {}).get("title", "Jogo"))
        recorde = dados.get("cheapestPriceEver", {})
        preco_rec_usd = recorde.get("price", "0")
        preco_rec_brl = formatar_brl(preco_rec_usd, cotacao)
        data_rec = datetime.fromtimestamp(int(recorde.get("date", 0))).strftime(
            "%d/%m/%Y"
        )

        ofertas_lojas = dados.get("deals", [])[:5]
        linhas = [
            f"📊 <b>Comparativo: {titulo}</b>",
            f"🏆 <b>Menor preço histórico:</b> {preco_rec_brl} (US$ {preco_rec_usd}) em {data_rec}\n",
            "🏪 <b>Preços por loja hoje:</b>",
        ]

        for oferta in ofertas_lojas:
            loja = html.escape(lojas.get(oferta["storeID"], "Loja digital"))
            p_usd = oferta["price"]
            p_brl = formatar_brl(p_usd, cotacao)
            desc = round(float(oferta["savings"]))
            link = (
                f"https://www.cheapshark.com/redirect?dealID={oferta['dealID']}"
            )
            tag_desc = f" (-{desc}%)" if desc > 0 else ""
            linhas.append(
                f"• <b>{loja}:</b> {p_brl} (US$ {p_usd}){tag_desc} — <a"
                f" href='{link}'>Link</a>"
            )

        bot.send_message(
            call.message.chat.id,
            "\n".join(linhas),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        bot.send_message(
            call.message.chat.id,
            "⚠️ Não foi possível carregar o comparativo desse jogo.",
        )


registrar_comandos()
print("Bot rodando com menu numerado... Pressione Ctrl+C no terminal para parar.")
bot.infinity_polling()