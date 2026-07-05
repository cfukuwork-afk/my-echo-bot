@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    
    # 役割を明確化：分析者としてのプロンプト
    prompt = f"""
    ユーザーの入力内容を分析し、以下の2点を出力してください。
    1. ユーザーの思考に対する洞察（短く）
    2. ユーザーの性格や行動パターンを示す「今日のキーワード」を1つだけ抽出
    
    入力内容: {user_text}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "あなたは分析のプロです。"},
                  {"role": "user", "content": prompt}]
    )
    
    ai_reply = response.choices[0].message.content
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
