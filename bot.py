import logging
import asyncio
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from database import Database
from config import BOT_TOKEN, ADMIN_IDS

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

# Conversation states
(
    REGISTER_NAME, REGISTER_AGE, REGISTER_GENDER,
    REGISTER_LOOKING_FOR, REGISTER_CITY, REGISTER_BIO,
    REGISTER_PHOTO, EDIT_MENU, EDIT_BIO, EDIT_PHOTO
) = range(10)


# ─────────────────────────────────────────
#  YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────

def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ["🔍 Keşfet", "❤️ Eşleşmelerim"],
        ["👤 Profilim", "⚙️ Ayarlar"],
        ["ℹ️ Yardım"]
    ], resize_keyboard=True)


async def send_profile_card(update_or_query, user_data: dict, show_buttons=True):
    """Bir kullanıcının profil kartını gönderir."""
    gender_emoji = "👨" if user_data['gender'] == 'Erkek' else "👩"
    text = (
        f"{gender_emoji} *{user_data['name']}*, {user_data['age']}\n"
        f"📍 {user_data['city']}\n"
        f"💬 {user_data['bio']}"
    )
    buttons = None
    if show_buttons:
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("❤️ Beğen", callback_data=f"like_{user_data['telegram_id']}"),
                InlineKeyboardButton("👎 Geç", callback_data=f"skip_{user_data['telegram_id']}")
            ]
        ])

    send = (
        update_or_query.message.reply_photo
        if hasattr(update_or_query, 'message')
        else update_or_query.edit_message_media
    )

    if user_data.get('photo_id'):
        if hasattr(update_or_query, 'message'):
            await update_or_query.message.reply_photo(
                photo=user_data['photo_id'],
                caption=text,
                parse_mode='Markdown',
                reply_markup=buttons
            )
        else:
            await update_or_query.message.reply_photo(
                photo=user_data['photo_id'],
                caption=text,
                parse_mode='Markdown',
                reply_markup=buttons
            )
    else:
        if hasattr(update_or_query, 'message'):
            await update_or_query.message.reply_text(
                text, parse_mode='Markdown', reply_markup=buttons
            )
        else:
            await update_or_query.message.reply_text(
                text, parse_mode='Markdown', reply_markup=buttons
            )


# ─────────────────────────────────────────
#  KAYIT SÜRECİ
# ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = db.get_user(user.id)

    if existing:
        await update.message.reply_text(
            f"👋 Tekrar hoş geldin, *{existing['name']}*!\n\nNe yapmak istersin?",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🎉 *Tanıştırma Botu'na Hoş Geldin!*\n\n"
        "Bu bot seni ilgi alanlarına göre yeni insanlarla tanıştırır.\n\n"
        "Başlamak için birkaç soruyu cevaplamanı isteyeceğim.\n\n"
        "📝 *Önce: Adın ne?*",
        parse_mode='Markdown'
    )
    return REGISTER_NAME


async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 30:
        await update.message.reply_text("❌ İsmin 2-30 karakter arasında olmalı. Tekrar yaz:")
        return REGISTER_NAME

    context.user_data['name'] = name
    await update.message.reply_text(f"Güzel isim, *{name}*! 😊\n\n📅 *Kaç yaşındasın?*", parse_mode='Markdown')
    return REGISTER_AGE


async def register_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if age < 18 or age > 99:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Geçerli bir yaş gir (18-99):")
        return REGISTER_AGE

    context.user_data['age'] = age
    keyboard = ReplyKeyboardMarkup([["👨 Erkek", "👩 Kadın"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("⚧ *Cinsiyetin nedir?*", parse_mode='Markdown', reply_markup=keyboard)
    return REGISTER_GENDER


async def register_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Erkek" in text:
        context.user_data['gender'] = 'Erkek'
    elif "Kadın" in text:
        context.user_data['gender'] = 'Kadın'
    else:
        await update.message.reply_text("❌ Lütfen butonlara bas.")
        return REGISTER_GENDER

    keyboard = ReplyKeyboardMarkup(
        [["👨 Erkek ara", "👩 Kadın ara"], ["🤝 Herkesi ara"]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text("🔍 *Kimi arıyorsun?*", parse_mode='Markdown', reply_markup=keyboard)
    return REGISTER_LOOKING_FOR


async def register_looking_for(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Erkek" in text:
        looking = 'Erkek'
    elif "Kadın" in text:
        looking = 'Kadın'
    elif "Herkes" in text or "Herkesi" in text:
        looking = 'Herkes'
    else:
        await update.message.reply_text("❌ Lütfen butonlara bas.")
        return REGISTER_LOOKING_FOR

    context.user_data['looking_for'] = looking
    await update.message.reply_text(
        "📍 *Hangi şehirdesin?*\n\nÖrnek: İstanbul, Ankara, İzmir",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return REGISTER_CITY


async def register_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip().title()
    if len(city) < 2:
        await update.message.reply_text("❌ Geçerli bir şehir adı gir:")
        return REGISTER_CITY

    context.user_data['city'] = city
    await update.message.reply_text(
        "💬 *Kendini kısaca tanıt:*\n\nİlgi alanların, ne arıyorsun, hobilerin... (max 200 karakter)",
        parse_mode='Markdown'
    )
    return REGISTER_BIO


async def register_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bio = update.message.text.strip()
    if len(bio) < 10 or len(bio) > 200:
        await update.message.reply_text("❌ Bio 10-200 karakter arasında olmalı:")
        return REGISTER_BIO

    context.user_data['bio'] = bio
    keyboard = ReplyKeyboardMarkup([["⏭️ Fotoğraf ekleme"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "📸 *Profil fotoğrafı ekle* (isteğe bağlı)\n\nBir fotoğraf gönder veya atla:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    return REGISTER_PHOTO


async def register_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_id = None

    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
    elif update.message.text and "atla" in update.message.text.lower():
        pass
    elif update.message.text and "Fotoğraf ekleme" in update.message.text:
        pass

    user = update.effective_user
    db.create_user(
        telegram_id=user.id,
        username=user.username or '',
        name=context.user_data['name'],
        age=context.user_data['age'],
        gender=context.user_data['gender'],
        looking_for=context.user_data['looking_for'],
        city=context.user_data['city'],
        bio=context.user_data['bio'],
        photo_id=photo_id
    )

    await update.message.reply_text(
        f"✅ *Profilin oluşturuldu, {context.user_data['name']}!*\n\n"
        "Artık insanları keşfetmeye başlayabilirsin. 🎉",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


# ─────────────────────────────────────────
#  KEŞFET SİSTEMİ
# ─────────────────────────────────────────

async def discover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    me = db.get_user(user_id)

    if not me:
        await update.message.reply_text("❌ Önce kayıt olmalısın. /start")
        return

    candidates = db.get_candidates(user_id, me['looking_for'], me['city'])

    if not candidates:
        await update.message.reply_text(
            "😔 Şu an gösterilecek kimse yok.\n\nBiraz sonra tekrar dene veya şehir filtresini kaldır!"
        )
        return

    context.user_data['candidates'] = candidates
    context.user_data['candidate_index'] = 0
    await show_next_candidate(update, context)


async def show_next_candidate(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    idx = context.user_data.get('candidate_index', 0)
    candidates = context.user_data.get('candidates', [])

    if idx >= len(candidates):
        msg = "🎉 Hepsini gördün! Biraz sonra tekrar keşfet."
        if hasattr(update_or_query, 'message'):
            await update_or_query.message.reply_text(msg, reply_markup=main_menu_keyboard())
        else:
            await update_or_query.message.reply_text(msg, reply_markup=main_menu_keyboard())
        return

    candidate = candidates[idx]
    await send_profile_card(update_or_query, candidate, show_buttons=True)


async def handle_like_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, target_id = query.data.split('_', 1)
    target_id = int(target_id)
    user_id = update.effective_user.id

    if action == 'like':
        match = db.add_like(user_id, target_id)
        if match:
            # Karşılıklı eşleşme!
            target = db.get_user(target_id)
            me = db.get_user(user_id)

            await query.message.reply_text(
                f"🎊 *EŞLEŞTİN!*\n\n*{target['name']}* de seni beğendi!\n\n"
                f"Ona mesaj atmak için: @{target.get('username', 'kullanıcı adı yok')}",
                parse_mode='Markdown'
            )

            # Karşı tarafa bildirim gönder
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"🎊 *EŞLEŞTİN!*\n\n*{me['name']}* de seni beğendi!\n\n"
                         f"Ona mesaj atmak için: @{me.get('username', 'kullanıcı adı yok')}",
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        else:
            await query.answer("❤️ Beğenildi!", show_alert=False)

    # Sonraki kişiyi göster
    context.user_data['candidate_index'] = context.user_data.get('candidate_index', 0) + 1
    await show_next_candidate(update, context)


# ─────────────────────────────────────────
#  EŞLEŞMELERİM
# ─────────────────────────────────────────

async def my_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    matches = db.get_matches(user_id)

    if not matches:
        await update.message.reply_text(
            "💔 Henüz eşleşmen yok.\n\nKeşfet bölümünden insanları beğen!",
            reply_markup=main_menu_keyboard()
        )
        return

    text = "❤️ *Eşleşmelerin:*\n\n"
    for m in matches:
        username_text = f"@{m['username']}" if m.get('username') else "_(kullanıcı adı yok)_"
        text += f"• *{m['name']}*, {m['age']} – {m['city']} → {username_text}\n"

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_menu_keyboard())


# ─────────────────────────────────────────
#  PROFİLİM
# ─────────────────────────────────────────

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    me = db.get_user(user_id)

    if not me:
        await update.message.reply_text("❌ Önce kayıt ol: /start")
        return

    await send_profile_card(update, me, show_buttons=False)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Bio Düzenle", callback_data="edit_bio")],
        [InlineKeyboardButton("📸 Fotoğraf Değiştir", callback_data="edit_photo")],
        [InlineKeyboardButton("🗑️ Hesabı Sil", callback_data="delete_account")]
    ])
    await update.message.reply_text("Ne yapmak istersin?", reply_markup=keyboard)


async def edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "edit_bio":
        await query.message.reply_text("✏️ Yeni bio'nu yaz (10-200 karakter):")
        return EDIT_BIO

    elif query.data == "edit_photo":
        await query.message.reply_text("📸 Yeni fotoğrafını gönder:")
        return EDIT_PHOTO

    elif query.data == "delete_account":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Evet, sil", callback_data="confirm_delete")],
            [InlineKeyboardButton("❌ İptal", callback_data="cancel_delete")]
        ])
        await query.message.reply_text("⚠️ Hesabını silmek istediğine emin misin?", reply_markup=keyboard)

    elif query.data == "confirm_delete":
        db.delete_user(update.effective_user.id)
        await query.message.reply_text("✅ Hesabın silindi. Tekrar kaydolmak için /start")

    elif query.data == "cancel_delete":
        await query.message.reply_text("İptal edildi.", reply_markup=main_menu_keyboard())

    return ConversationHandler.END


async def save_new_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bio = update.message.text.strip()
    if len(bio) < 10 or len(bio) > 200:
        await update.message.reply_text("❌ Bio 10-200 karakter arasında olmalı:")
        return EDIT_BIO

    db.update_user(update.effective_user.id, bio=bio)
    await update.message.reply_text("✅ Bio güncellendi!", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def save_new_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Lütfen bir fotoğraf gönder:")
        return EDIT_PHOTO

    photo_id = update.message.photo[-1].file_id
    db.update_user(update.effective_user.id, photo_id=photo_id)
    await update.message.reply_text("✅ Fotoğraf güncellendi!", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ─────────────────────────────────────────
#  YARDIM & DİĞER
# ─────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Yardım Menüsü*\n\n"
        "🔍 *Keşfet* – Sana uygun kişileri gör, beğen veya geç\n"
        "❤️ *Eşleşmelerim* – Karşılıklı beğenilerin\n"
        "👤 *Profilim* – Profilini gör ve düzenle\n"
        "⚙️ *Ayarlar* – Filtreler (yakında)\n\n"
        "Sorun yaşıyorsan: @yönetici_adı",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Ayarlar yakında eklenecek!\n\n"
        "Şehir filtresi, yaş aralığı gibi özellikler geliyor...",
        reply_markup=main_menu_keyboard()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ İşlem iptal edildi.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ─────────────────────────────────────────
#  ADMİN KOMUTLARI
# ─────────────────────────────────────────

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    stats = db.get_stats()
    await update.message.reply_text(
        f"📊 *Bot İstatistikleri*\n\n"
        f"👥 Toplam kullanıcı: {stats['users']}\n"
        f"❤️ Toplam beğeni: {stats['likes']}\n"
        f"🎊 Toplam eşleşme: {stats['matches']}",
        parse_mode='Markdown'
    )


# ─────────────────────────────────────────
#  ANA FONKSİYON
# ─────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Kayıt ConversationHandler
    register_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_age)],
            REGISTER_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_gender)],
            REGISTER_LOOKING_FOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_looking_for)],
            REGISTER_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_city)],
            REGISTER_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_bio)],
            REGISTER_PHOTO: [
                MessageHandler(filters.PHOTO, register_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_photo)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Profil düzenleme ConversationHandler
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_callback, pattern='^edit_')],
        states={
            EDIT_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_bio)],
            EDIT_PHOTO: [MessageHandler(filters.PHOTO, save_new_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(register_conv)
    app.add_handler(edit_conv)

    # Buton callback'leri
    app.add_handler(CallbackQueryHandler(handle_like_skip, pattern='^(like|skip)_'))
    app.add_handler(CallbackQueryHandler(edit_callback, pattern='^(confirm_delete|cancel_delete|delete_account)$'))

    # Menü butonları
    app.add_handler(MessageHandler(filters.Regex("^🔍 Keşfet$"), discover))
    app.add_handler(MessageHandler(filters.Regex("^❤️ Eşleşmelerim$"), my_matches))
    app.add_handler(MessageHandler(filters.Regex("^👤 Profilim$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Ayarlar$"), settings))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Yardım$"), help_command))

    # Komutlar
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('stats', admin_stats))

    print("🤖 Bot başlatıldı...")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
