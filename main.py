import os
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from supabase import create_client
from openai import OpenAI
import datetime

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

user_diagnoses = {}

# 10問に増やしました
QUESTIONS = [
    "1. 社交的な集まりでは、積極的に会話の中心に入る方だ。(1:そう思う〜5:そう思わない)",
    "2. 未来の計画よりも、今の瞬間を楽しむ方が好きだ。",
    "3. 自分の考えを言葉にする前に、頭の中でじっくり整理したい。",
    "4. 論理的な一貫性を、感情的な調和よりも重視する。",
    "5. 締め切り直前に集中して作業する方が効率的だ。",
    "6. 新しい環境に飛び込むことに対して、ワクワクする気持ちの方が大きい。",
    "7. 抽象的なアイデアや哲学的な議論をするのが楽しい。",
    "8. 計画は柔軟に変更可能であるべきだと考えている。",
    "9. 他人からの評価は、自分自身の納得感よりも重要だ。",
    "10. 自分の感情よりも、客観的な事実を優先して判断する。"
]

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
    
    if text == "占い":
        today = datetime.date.today().strftime("%Y年%m月%d日")
        prompt = f"今日は{today}。ラッキーカラーとラッキーアクションを含む今日の運勢を短く教えて。"
        res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res.choices[0].message.content))
        return

    if text == "診断開始":
        user_diagnoses[user_id] = {"answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"MBTI診断開始！\n{QUESTIONS[0]}"
        ))
        return

    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        d["answers"].append(text)
        
        # 10問答えたかチェック
        if len(d["answers"]) < 10:
            next_q = QUESTIONS[len(d["answers"])]
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【{len(d['answers'])+1}/10】\n{next_q}"))
        else:
            # 終了処理
            line_bot_api.push_message(user_id, TextSendMessage(text="全10問終了！結果を分析中です..."))
            prompt = f"回答:{d['answers']}。この回答からMBTIタイプを判定し、専属コーチとして詳細な分析結果を伝えて。"
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            result = res.choices[0].message.content
            
            supabase.table("logs").insert({"user_id": user_id, "message": "診断結果", "ai_reply": result}).execute()
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【診断完了！】\n{result}"))
            del user_diagnoses[user_id]
        return

    # 通常モード
    res = supabase.table("logs").select("ai_reply").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
    profile = res.data[0]['ai_reply'] if res.data else "未診断"
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": f"専属コーチ。性格:{profile}。この結果に基づき相談に乗って。"},
        {"role": "user", "content": text}
    ])
    supabase.table("logs").insert({"user_id": user_id, "message": text, "ai_reply": ai_resp.choices[0].message.content}).execute()
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_resp.choices[0].message.content))
