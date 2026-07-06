import os
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from supabase import create_client
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

user_diagnoses = {}

# 100問のリスト（後で具体的内容に差し替え可能）
QUESTIONS = [f"質問{i}: 1(そう思わない)〜5(そう思う)で答えて。" for i in range(1, 101)]

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    handler.handle(body.decode("utf-8"), signature)
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text
    
    # 診断開始
    if text == "診断開始":
        user_diagnoses[user_id] = {"answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"【MBTI 100問診断：開始】\n{QUESTIONS[0]}\n※回答を入力すると即座に次へ進みます。"
        ))
        return

    # 診断中ロジック
    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        d["answers"].append(text)
        
        current_idx = len(d["answers"])
        if current_idx < 100:
            # テンポよくpush_messageで次を送る
            line_bot_api.push_message(user_id, TextSendMessage(
                text=f"【{current_idx + 1}/100】\n{QUESTIONS[current_idx]}"
            ))
        else:
            # 診断終了と分析
            line_bot_api.push_message(user_id, TextSendMessage(text="全100問終了！統計的に分析しています..."))
            prompt = f"回答:{d['answers']}。この回答からMBTIタイプを特定し、性格特性をコーチとして分析せよ。"
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            analysis = res.choices[0].message.content
            
            supabase.table("logs").insert({"user_id": user_id, "message": "診断結果", "ai_reply": analysis}).execute()
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【診断完了】\n{analysis}"))
            del user_diagnoses[user_id]
        return

    # 通常モード（コーチング）
    res = supabase.table("logs").select("ai_reply").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
    profile = res.data[0]['ai_reply'] if res.data else "未診断"
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": f"あなたはユーザーの性格を把握したコーチ。性格:{profile}。この特性を活かして相談に乗れ。"},
        {"role": "user", "content": text}
    ])
    supabase.table("logs").insert({"user_id": user_id, "message": text, "ai_reply": ai_resp.choices[0].message.content}).execute()
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_resp.choices[0].message.content))
