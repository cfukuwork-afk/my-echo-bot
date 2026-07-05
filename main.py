@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text

    # 【重要】診断モードの判定を最優先かつ厳密にする
    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        
        if d["step"] == 1:
            d["answers"].append(text)
            d["step"] = 2
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="【2/3】チームでの役割は？"))
            return  # ここで確実に終了させる

        if d["step"] == 2:
            d["answers"].append(text)
            d["step"] = 3
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="【3/3】休日の過ごし方は？"))
            return  # ここで確実に終了させる

        if d["step"] == 3:
            d["answers"].append(text)
            # 診断終了処理
            prompt = f"性格診断の回答です: {d['answers']}。この回答から性格タイプを1つ判定し、一言で結果を伝えて。"
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            personality = res.choices[0].message.content
            
            # DB保存（テーブル名を確認してください）
            supabase.table("profiles").upsert({"user_id": user_id, "personality_type": personality}).execute()
            
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"診断完了！あなたのタイプは「{personality}」です。"))
            del user_diagnoses[user_id]
            return # ここで終了

    # 診断開始用コマンド
    if text == "診断開始":
        user_diagnoses[user_id] = {"step": 1, "answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="【1/3】仕事で何を重視しますか？"))
        return

    # 通常分析（診断が完了しているユーザーのみ）
    # ... 以下、通常分析の処理 ...
