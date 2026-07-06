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

# MBTI診断用の質問リスト（5問）
QUESTIONS = [
    "質問1: 社交的な集まりでは、積極的に会話の中心に入る方だ。(1:そう思う〜5:そう思わない)",
    "質問2: 未来の計画よりも、今の瞬間を楽しむ方が好きだ。(1:そう思う〜5:そう思わない)",
    "質問3: 自分の考えを言葉にする前に、頭の中でじっくり整理したい。(1:そう思う〜5:そう思わない)",
    "質問4: 論理的な一貫性を、感情的な調和よりも重視する。(1:そう思う〜5:そう思わない)",
    "質問5: 締め切り直前に集中して作業する方が効率的だ。(1:そう思う〜5:そう思わない)",
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
    text = event.text

    # 1. 占い機能（占いと打つと今日の運勢を出す）
    if text == "占い":
        today = datetime.date.today().strftime("%Y年%m月%d日")
        prompt = f"今日は{today}。今日のラッキーカラー、ラッキーアクションを含む占いを教えて。"
        res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res.choices[0].message.content))
        return

    # 2. 診断開始
    if text == "診断開始":
        user_diagnoses[user_id] = {"answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"MBTI診断を開始します！\n{QUESTIONS[0]}\n(回答を入力してください)"
        ))
        return

    # 3. 診断中ロジック
    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        d["answers"].append(text)
        
        if len(d["answers"]) < 5:
            next_q = QUESTIONS[len(d["answers"])]
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【{len(d['answers'])+1}/5】\n{next_q}"))
        else:
            # 5問終了！分析実行
            prompt = f"MBTI診断回答:{d['answers']}。この回答からMBTIタイプを判定し、あなたの専属コーチとして詳細な分析結果を一言で伝えて。"
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            result = res.choices[0].message.content
            
            # 保存して結果を返す
            supabase.table("logs").insert({"user_id": user_id, "message": "診断結果", "ai_reply": result}).execute()
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【診断完了！】\n{result}"))
            del user_diagnoses[user_id]
        return

    # 4. 通常コーチモード
    res = supabase.table("logs").select("ai_reply").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
    profile = res.data[0]['ai_reply'] if res.data else "未診断"
    
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": f"あなたはユーザーの専属コーチ。性格分析結果:{profile}。この結果に基づき親身に相談に乗って。"},
        {"role": "user", "content": text}
    ])
    
    supabase.table("logs").insert({"user_id": user_id, "message": text, "ai_reply": ai_resp.choices[0].message.content}).execute()
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_resp.choices[0].message.content))
