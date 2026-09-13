# import json
# import os
# import uuid

# import psycopg2
# import razorpay
# import requests

# from dotenv import load_dotenv
# from flask import Flask, jsonify, request
# from psycopg2.extras import RealDictCursor


# # ============================================================
# # ENVIRONMENT
# # ============================================================

# load_dotenv()

# ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
# PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
# VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
# RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# DATABASE_URL = os.getenv("DATABASE_URL")


# # ============================================================
# # FLASK APP
# # ============================================================

# app = Flask(__name__)


# # ============================================================
# # RAZORPAY
# # ============================================================

# rzp_client = razorpay.Client(
#     auth=(
#         RAZORPAY_KEY_ID,
#         RAZORPAY_KEY_SECRET,
#     )
# )


# # ============================================================
# # DATABASE
# # ============================================================

# def get_db_connection():

#     return psycopg2.connect(
#         DATABASE_URL
#     )


# # ============================================================
# # META WHATSAPP REQUEST
# # ============================================================

# def _send_meta_payload(
#     payload: dict,
# ):

#     url = (
#         "https://graph.facebook.com/"
#         f"v20.0/{PHONE_NUMBER_ID}/messages"
#     )

#     headers = {
#         "Authorization": (
#             f"Bearer {ACCESS_TOKEN}"
#         ),
#         "Content-Type":
#             "application/json",
#     }

#     return requests.post(
#         url,
#         headers=headers,
#         json=payload,
#         timeout=20,
#     )


# # ============================================================
# # WHATSAPP WEBHOOK
# # ============================================================

# @app.route(
#     "/webhook",
#     methods=[
#         "GET",
#         "POST",
#     ],
# )
# def webhook():

#     # Meta verification
#     if request.method == "GET":

#         mode = request.args.get(
#             "hub.mode"
#         )

#         token = request.args.get(
#             "hub.verify_token"
#         )

#         challenge = request.args.get(
#             "hub.challenge"
#         )

#         if (
#             mode == "subscribe"
#             and token == VERIFY_TOKEN
#         ):

#             return challenge, 200

#         return "Forbidden", 403


#     # Incoming WhatsApp message
#     data = request.get_json(
#         silent=True
#     ) or {}

#     try:

#         if (
#             data.get("entry")
#             and data["entry"][0].get(
#                 "changes"
#             )
#         ):

#             value = (
#                 data["entry"][0]
#                 ["changes"][0]
#                 ["value"]
#             )

#             messages = value.get(
#                 "messages",
#                 [],
#             )

#             if messages:

#                 process_message(
#                     messages[0]
#                 )

#     except Exception as exc:

#         print(
#             "Error processing "
#             "Meta webhook:",
#             exc,
#         )


#     return jsonify(
#         {
#             "status": "success"
#         }
#     ), 200


# # ============================================================
# # RAZORPAY WEBHOOK
# # ============================================================

# @app.route(
#     "/razorpay-webhook",
#     methods=["POST"],
# )
# def razorpay_webhook():

#     data = request.get_json(
#         silent=True
#     ) or {}

#     try:

#         if (
#             data.get("event")
#             != "payment_link.paid"
#         ):

#             return jsonify(
#                 {
#                     "status": "ignored"
#                 }
#             ), 200


#         entity = (
#             data["payload"]
#             ["payment_link"]
#             ["entity"]
#         )

#         notes = entity.get(
#             "notes",
#             {},
#         )

#         order_id = notes.get(
#             "order_id"
#         )

#         sender_phone = notes.get(
#             "phone_number"
#         )


#         conn = get_db_connection()

#         cur = conn.cursor(
#             cursor_factory=RealDictCursor
#         )


#         # ----------------------------------------------------
#         # MARK ORDER PAID
#         # ----------------------------------------------------

#         cur.execute(
#             """
#             UPDATE orders

#             SET
#                 status = 'Paid',
#                 paid_at = NOW(),
#                 updated_at = NOW()

#             WHERE
#                 order_id = %s
#                 AND status = 'Pending'

#             RETURNING cart_items
#             """,
#             (
#                 order_id,
#             ),
#         )


#         order = cur.fetchone()


#         # ----------------------------------------------------
#         # REDUCE INVENTORY
#         # ----------------------------------------------------

#         if order:

#             cart = (
#                 order["cart_items"]
#                 or []
#             )

#             for item in cart:

#                 cur.execute(
#                     """
#                     UPDATE menu

#                     SET inventory =
#                         inventory - %s

#                     WHERE id = %s
#                     """,
#                     (
#                         item["qty"],
#                         item["id"],
#                     ),
#                 )


#         # ----------------------------------------------------
#         # CLEAR WHATSAPP SESSION
#         # ----------------------------------------------------

#         if sender_phone:

#             cur.execute(
#                 """
#                 DELETE FROM sessions

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     sender_phone,
#                 ),
#             )


#         conn.commit()

#         cur.close()

#         conn.close()


#         # ----------------------------------------------------
#         # PAYMENT CONFIRMATION MESSAGE
#         # ----------------------------------------------------

#         if sender_phone:

#             send_reply(
#                 sender_phone,
#                 (
#                     "✅ *Payment Successful!*\n\n"
#                     f"Your order ({order_id}) "
#                     "has been placed successfully.\n\n"
#                     "The kitchen will start "
#                     "preparing your order shortly.\n\n"
#                     "Thank you for choosing "
#                     "Watave's Biriyani Point!"
#                 ),
#             )


#     except Exception as exc:

#         print(
#             "Error processing "
#             "Razorpay webhook:",
#             exc,
#         )


#     return jsonify(
#         {
#             "status": "ok"
#         }
#     ), 200


# # ============================================================
# # WHATSAPP BOT
# # ============================================================

# def process_message(
#     message: dict,
# ):

#     sender_phone = message[
#         "from"
#     ]

#     msg_type = message.get(
#         "type"
#     )

#     incoming_text = ""

#     interactive_id = ""


#     # --------------------------------------------------------
#     # TEXT MESSAGE
#     # --------------------------------------------------------

#     if msg_type == "text":

#         incoming_text = (
#             message.get(
#                 "text",
#                 {},
#             )
#             .get(
#                 "body",
#                 "",
#             )
#             .strip()
#             .lower()
#         )


#     # --------------------------------------------------------
#     # BUTTON / LIST REPLY
#     # --------------------------------------------------------

#     elif msg_type == "interactive":

#         interactive = message.get(
#             "interactive",
#             {},
#         )

#         interactive_type = (
#             interactive.get(
#                 "type"
#             )
#         )


#         if (
#             interactive_type
#             == "button_reply"
#         ):

#             interactive_id = (
#                 interactive
#                 .get(
#                     "button_reply",
#                     {},
#                 )
#                 .get(
#                     "id",
#                     "",
#                 )
#             )


#         elif (
#             interactive_type
#             == "list_reply"
#         ):

#             interactive_id = (
#                 interactive
#                 .get(
#                     "list_reply",
#                     {},
#                 )
#                 .get(
#                     "id",
#                     "",
#                 )
#             )


#     conn = get_db_connection()

#     cur = conn.cursor(
#         cursor_factory=RealDictCursor
#     )


#     # ========================================================
#     # GET CURRENT SESSION
#     # ========================================================

#     cur.execute(
#         """
#         SELECT *

#         FROM sessions

#         WHERE phone_number = %s
#         """,
#         (
#             sender_phone,
#         ),
#     )

#     session = cur.fetchone()


#     # ========================================================
#     # START / RESTART
#     # ========================================================

#     start_words = {
#         "hi",
#         "hello",
#         "start",
#         "restart",
#     }

#     is_start = (
#         incoming_text
#         in start_words
#     )


#     if is_start:

#         if session:

#             cur.execute(
#                 """
#                 DELETE FROM sessions

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     sender_phone,
#                 ),
#             )

#             conn.commit()

#         session = None


#     # ========================================================
#     # NEW SESSION
#     # ========================================================

#     if not session:

#         if not is_start:

#             send_reply(
#                 sender_phone,
#                 (
#                     "Welcome to Watave's "
#                     "Biriyani Point! 🍛\n\n"
#                     "Say *Hi* to place "
#                     "your order."
#                 ),
#             )

#             cur.close()
#             conn.close()

#             return


#         cur.execute(
#             """
#             INSERT INTO users (
#                 phone_number
#             )

#             VALUES (%s)

#             ON CONFLICT DO NOTHING
#             """,
#             (
#                 sender_phone,
#             ),
#         )


#         cur.execute(
#             """
#             INSERT INTO sessions (
#                 phone_number,
#                 step
#             )

#             VALUES (
#                 %s,
#                 'CHOOSE_DINING'
#             )

#             RETURNING *
#             """,
#             (
#                 sender_phone,
#             ),
#         )


#         session = cur.fetchone()

#         conn.commit()


#         send_button_message(
#             sender_phone,
#             (
#                 "Are you ordering for "
#                 "Takeaway or Dine-in?"
#             ),
#             [
#                 {
#                     "id": "takeaway",
#                     "title": "🥡 Takeaway",
#                 },
#                 {
#                     "id": "dine_in",
#                     "title": "🍽️ Dine-in",
#                 },
#             ],
#         )


#         cur.close()
#         conn.close()

#         return


#     step = session[
#         "step"
#     ]


#     # ========================================================
#     # CHOOSE DINING
#     # ========================================================

#     if step == "CHOOSE_DINING":

#         if (
#             interactive_id
#             == "takeaway"
#         ):

#             cur.execute(
#                 """
#                 UPDATE sessions

#                 SET
#                     order_type = 'Takeaway',
#                     step = 'SHOW_MENU'

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     sender_phone,
#                 ),
#             )

#             show_menu(
#                 sender_phone,
#                 cur,
#             )


#         elif (
#             interactive_id
#             == "dine_in"
#         ):

#             cur.execute(
#                 """
#                 UPDATE sessions

#                 SET
#                     order_type = 'Dine-in',
#                     step = 'ENTER_TABLE'

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     sender_phone,
#                 ),
#             )

#             send_reply(
#                 sender_phone,
#                 "Please enter your Table Number:",
#             )


#         else:

#             send_reply(
#                 sender_phone,
#                 (
#                     "Please tap one of "
#                     "the buttons above."
#                 ),
#             )


#     # ========================================================
#     # TABLE NUMBER
#     # ========================================================

#     elif step == "ENTER_TABLE":

#         if msg_type == "text":

#             table_number = (
#                 message["text"]
#                 ["body"]
#                 .strip()
#             )

#             cur.execute(
#                 """
#                 UPDATE sessions

#                 SET
#                     table_number = %s,
#                     step = 'SHOW_MENU'

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     table_number,
#                     sender_phone,
#                 ),
#             )

#             show_menu(
#                 sender_phone,
#                 cur,
#             )


#     # ========================================================
#     # MENU ITEM SELECTION
#     # ========================================================

#     elif step in {
#         "SHOW_MENU",
#         "CHOOSE_ITEM",
#     }:

#         if interactive_id:

#             cur.execute(
#                 """
#                 UPDATE sessions

#                 SET
#                     temp_item_id = %s,
#                     step = 'CHOOSE_QUANTITY'

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     int(
#                         interactive_id
#                     ),
#                     sender_phone,
#                 ),
#             )


#             send_reply(
#                 sender_phone,
#                 (
#                     "How many plates "
#                     "would you like?\n"
#                     "Please type a number."
#                 ),
#             )


#     # ========================================================
#     # QUANTITY
#     # ========================================================

#     elif step == "CHOOSE_QUANTITY":

#         if msg_type == "text":

#             try:

#                 qty = int(
#                     incoming_text
#                 )

#                 if qty <= 0:
#                     raise ValueError

#             except ValueError:

#                 send_reply(
#                     sender_phone,
#                     (
#                         "Please enter a valid "
#                         "quantity of 1 or more."
#                     ),
#                 )

#                 cur.close()
#                 conn.close()

#                 return


#             item_id = session[
#                 "temp_item_id"
#             ]


#             cur.execute(
#                 """
#                 SELECT *

#                 FROM menu

#                 WHERE
#                     id = %s
#                     AND is_active = TRUE
#                 """,
#                 (
#                     item_id,
#                 ),
#             )


#             item = cur.fetchone()


#             if not item:

#                 send_reply(
#                     sender_phone,
#                     (
#                         "Sorry, that item "
#                         "is no longer available."
#                     ),
#                 )

#                 cur.close()
#                 conn.close()

#                 return


#             if qty > item[
#                 "inventory"
#             ]:

#                 send_reply(
#                     sender_phone,
#                     (
#                         "Sorry, we only have "
#                         f"{item['inventory']} "
#                         f"plates of {item['name']} "
#                         "available."
#                     ),
#                 )

#                 cur.close()
#                 conn.close()

#                 return


#             cart = (
#                 session["cart"]
#                 or []
#             )


#             cart.append(
#                 {
#                     "id":
#                         item["id"],

#                     "name":
#                         item["name"],

#                     "price":
#                         item["price"],

#                     "qty":
#                         qty,
#                 }
#             )


#             cur.execute(
#                 """
#                 UPDATE sessions

#                 SET
#                     cart = %s,
#                     step = 'CART_OPTIONS'

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     json.dumps(
#                         cart
#                     ),
#                     sender_phone,
#                 ),
#             )


#             total = sum(
#                 item["price"]
#                 * item["qty"]
#                 for item in cart
#             )


#             summary = (
#                 "🛒 *Cart Preview*\n\n"
#             )


#             for cart_item in cart:

#                 summary += (
#                     f"• {cart_item['qty']}x "
#                     f"{cart_item['name']} "
#                     f"- ₹"
#                     f"{cart_item['price'] * cart_item['qty']}"
#                     "\n"
#                 )


#             summary += (
#                 f"\n*Total: ₹{total}*"
#             )


#             send_button_message(
#                 sender_phone,
#                 summary,
#                 [
#                     {
#                         "id": "add_item",
#                         "title": "➕ Add Item",
#                     },
#                     {
#                         "id": "checkout",
#                         "title": "💳 Checkout",
#                     },
#                     {
#                         "id": "cancel",
#                         "title": "❌ Cancel",
#                     },
#                 ],
#             )


#     # ========================================================
#     # CART OPTIONS
#     # ========================================================

#     elif step == "CART_OPTIONS":

#         if (
#             interactive_id
#             == "add_item"
#         ):

#             cur.execute(
#                 """
#                 UPDATE sessions

#                 SET step = 'SHOW_MENU'

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     sender_phone,
#                 ),
#             )


#             show_menu(
#                 sender_phone,
#                 cur,
#             )


#         elif (
#             interactive_id
#             == "cancel"
#         ):

#             cur.execute(
#                 """
#                 DELETE FROM sessions

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     sender_phone,
#                 ),
#             )


#             send_reply(
#                 sender_phone,
#                 (
#                     "Order cancelled. "
#                     "Say *Hi* whenever "
#                     "you are hungry again!"
#                 ),
#             )


#         elif (
#             interactive_id
#             == "checkout"
#         ):

#             cart = (
#                 session["cart"]
#                 or []
#             )


#             if not cart:

#                 send_reply(
#                     sender_phone,
#                     "Your cart is empty.",
#                 )

#                 cur.close()
#                 conn.close()

#                 return


#             total = sum(
#                 item["price"]
#                 * item["qty"]
#                 for item in cart
#             )


#             order_id = (
#                 "ORD-"
#                 + uuid.uuid4()
#                 .hex[:6]
#                 .upper()
#             )


#             # ------------------------------------------------
#             # CREATE PENDING ORDER
#             # ------------------------------------------------

#             cur.execute(
#                 """
#                 INSERT INTO orders (
#                     order_id,
#                     phone_number,
#                     order_type,
#                     table_number,
#                     total_amount,
#                     cart_items,
#                     status
#                 )

#                 VALUES (
#                     %s,
#                     %s,
#                     %s,
#                     %s,
#                     %s,
#                     %s,
#                     'Pending'
#                 )
#                 """,
#                 (
#                     order_id,
#                     sender_phone,
#                     session[
#                         "order_type"
#                     ],
#                     session[
#                         "table_number"
#                     ],
#                     total,
#                     json.dumps(
#                         cart
#                     ),
#                 ),
#             )


#             # ------------------------------------------------
#             # RAZORPAY PAYMENT LINK
#             # ------------------------------------------------

#             payment_link_data = {

#                 "amount":
#                     total * 100,

#                 "currency":
#                     "INR",

#                 "description":
#                     (
#                         "Watave's "
#                         "Biriyani Point"
#                     ),

#                 "customer": {
#                     "contact":
#                         f"+{sender_phone}"
#                 },

#                 "notes": {
#                     "order_id":
#                         order_id,

#                     "phone_number":
#                         sender_phone,
#                 },
#             }


#             payment_link = (
#                 rzp_client
#                 .payment_link
#                 .create(
#                     payment_link_data
#                 )
#             )


#             link = (
#                 payment_link[
#                     "short_url"
#                 ]
#             )


#             send_reply(
#                 sender_phone,
#                 (
#                     "🧾 *Final Checkout*\n\n"
#                     f"Order: {order_id}\n"
#                     f"Total Amount: ₹{total}\n\n"
#                     "Please use the link "
#                     "below to pay and "
#                     "confirm your order:\n"
#                     f"{link}"
#                 ),
#             )


#             cur.execute(
#                 """
#                 UPDATE sessions

#                 SET step =
#                     'AWAITING_PAYMENT'

#                 WHERE phone_number = %s
#                 """,
#                 (
#                     sender_phone,
#                 ),
#             )


#     # ========================================================
#     # WAITING FOR PAYMENT
#     # ========================================================

#     elif (
#         step
#         == "AWAITING_PAYMENT"
#     ):

#         send_reply(
#             sender_phone,
#             (
#                 "Payment confirmation is "
#                 "still pending.\n\n"
#                 "Please complete the payment, "
#                 "or send *Restart* to begin again."
#             ),
#         )


#     conn.commit()

#     cur.close()

#     conn.close()


# # ============================================================
# # SHOW MENU
# # ============================================================

# def show_menu(
#     phone_number,
#     cur,
# ):

#     cur.execute(
#         """
#         SELECT *

#         FROM menu

#         WHERE
#             inventory > 0
#             AND is_active = TRUE

#         ORDER BY name
#         """
#     )


#     items = cur.fetchall()


#     if not items:

#         send_reply(
#             phone_number,
#             (
#                 "Sorry, we are completely "
#                 "sold out right now! 😔"
#             ),
#         )

#         return


#     rows = [
#         {
#             "id":
#                 str(
#                     item["id"]
#                 ),

#             "title":
#                 item["name"],

#             "description":
#                 f"₹{item['price']}",
#         }
#         for item in items
#     ]


#     payload = {

#         "messaging_product":
#             "whatsapp",

#         "to":
#             phone_number,

#         "type":
#             "interactive",

#         "interactive": {

#             "type":
#                 "list",

#             "body": {
#                 "text":
#                     (
#                         "Please select an "
#                         "item from our menu:"
#                     )
#             },

#             "action": {

#                 "button":
#                     "View Menu",

#                 "sections": [
#                     {
#                         "title":
#                             "Available Items",

#                         "rows":
#                             rows,
#                     }
#                 ],
#             },
#         },
#     }


#     _send_meta_payload(
#         payload
#     )


# # ============================================================
# # BUTTON MESSAGE
# # ============================================================

# def send_button_message(
#     phone_number,
#     text,
#     buttons,
# ):

#     payload = {

#         "messaging_product":
#             "whatsapp",

#         "to":
#             phone_number,

#         "type":
#             "interactive",

#         "interactive": {

#             "type":
#                 "button",

#             "body": {
#                 "text":
#                     text
#             },

#             "action": {

#                 "buttons": [
#                     {
#                         "type":
#                             "reply",

#                         "reply": {
#                             "id":
#                                 button[
#                                     "id"
#                                 ],

#                             "title":
#                                 button[
#                                     "title"
#                                 ],
#                         },
#                     }
#                     for button
#                     in buttons
#                 ],
#             },
#         },
#     }


#     _send_meta_payload(
#         payload
#     )


# # ============================================================
# # TEXT MESSAGE
# # ============================================================

# def send_reply(
#     phone_number,
#     text_message,
# ):

#     payload = {

#         "messaging_product":
#             "whatsapp",

#         "to":
#             phone_number,

#         "type":
#             "text",

#         "text": {
#             "body":
#                 text_message
#         },
#     }


#     _send_meta_payload(
#         payload
#     )


# # ============================================================
# # OPTIONAL DIRECT FLASK RUN
# # ============================================================

# if __name__ == "__main__":

#     app.run(
#         port=5000,
#         debug=True,
#     )
