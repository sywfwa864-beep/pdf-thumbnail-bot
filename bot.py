import os
import asyncio
from pathlib import Path
from PIL import Image
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

TMP = Path("/tmp/pdf_thumb_bot")
TMP.mkdir(parents=True, exist_ok=True)

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {}
    await update.message.reply_text(
        "أهلاً 👋\n\n"
        "ابعت ملف PDF الأول، وبعده ابعت الصورة اللي عايزها كصورة معاينة.\n"
        "هارجعلك نفس الـPDF بدون إضافة الصورة داخله."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        return
    doc = update.message.document
    if doc.mime_type != "application/pdf" and not (doc.file_name or "").lower().endswith(".pdf"):
        await update.message.reply_text("ابعت ملف PDF فقط 📄")
        return

    uid = update.effective_user.id
    folder = TMP / str(uid)
    folder.mkdir(parents=True, exist_ok=True)
    pdf_path = folder / "document.pdf"

    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(str(pdf_path))

    user_data[uid] = {"pdf": str(pdf_path)}
    await update.message.reply_text("تمام ✅ دلوقتي ابعت الصورة اللي عايزها كـThumbnail 🖼️")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = user_data.get(uid, {})
    if "pdf" not in data:
        await update.message.reply_text("ابعت الـPDF الأول 📄")
        return

    folder = TMP / str(uid)
    thumb = folder / "thumb.jpg"

    # Telegram requires a JPEG thumbnail no larger than 320x320 and under 200 KB.
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    original = folder / "original_image"
    await tg_file.download_to_drive(str(original))

    img = Image.open(original).convert("RGB")
    img.thumbnail((320, 320), Image.Resampling.LANCZOS)

    quality = 90
    while True:
        img.save(thumb, "JPEG", quality=quality, optimize=True)
        if thumb.stat().st_size <= 190_000 or quality <= 30:
            break
        quality -= 5

    # The Bot API accepts a thumbnail separately when sending a document.
    with open(data["pdf"], "rb") as pdf, open(thumb, "rb") as th:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf,
            thumbnail=th,
            caption="تم تجهيز الملف ✅"
        )

    try:
        for p in folder.iterdir():
            p.unlink()
        folder.rmdir()
    except Exception:
        pass

    user_data.pop(uid, None)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "طريقة الاستخدام:\n"
        "1) ابعت PDF\n"
        "2) ابعت الصورة\n"
        "3) هيرجع نفس الـPDF مع Thumbnail خارجي."
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
