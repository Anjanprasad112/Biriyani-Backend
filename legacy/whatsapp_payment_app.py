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


import json
import os
import uuid

import psycopg2
import razorpay
import requests

from flask import (
    Flask,
    jsonify,
    request,
)

from psycopg2.extras import RealDictCursor


app = Flask(__name__)


# ============================================================
# CORS FOR LEGACY ROUTES
# ============================================================

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get(
        "Origin"
    )

    allowed_origins = {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://biriyani-frontend-ten.vercel.app",
    }

    if origin in allowed_origins:
        response.headers[
            "Access-Control-Allow-Origin"
        ] = origin

        response.headers[
            "Access-Control-Allow-Headers"
        ] = "Content-Type"

        response.headers[
            "Access-Control-Allow-Methods"
        ] = "GET, POST, PATCH, DELETE, OPTIONS"

    return response


# ============================================================
# CONFIG
# ============================================================

ACCESS_TOKEN = os.environ.get(
    "ACCESS_TOKEN"
)

PHONE_NUMBER_ID = os.environ.get(
    "PHONE_NUMBER_ID"
)

VERIFY_TOKEN = os.environ.get(
    "VERIFY_TOKEN"
)


RAZORPAY_KEY_ID = os.environ.get(
    "RAZORPAY_KEY_ID"
)

RAZORPAY_KEY_SECRET = os.environ.get(
    "RAZORPAY_KEY_SECRET"
)


# Keep configurable so the Graph API version can be changed
# through environment config without rewriting business logic.
WHATSAPP_GRAPH_VERSION = os.environ.get(
    "WHATSAPP_GRAPH_VERSION",
    "v20.0",
)


rzp_client = razorpay.Client(
    auth=(
        RAZORPAY_KEY_ID,
        RAZORPAY_KEY_SECRET,
    )
)


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    return psycopg2.connect(
        os.environ.get(
            "DATABASE_URL"
        )
    )


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def home():
    return {
        "status": "ok"
    }


@app.route(
    "/health",
    methods=["GET"],
)
def health_check():
    return jsonify(
        {
            "status": "ok"
        }
    ), 200


# ============================================================
# WHATSAPP WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=[
        "GET",
        "POST",
    ],
)
def webhook():
    if request.method == "GET":
        if (
            request.args.get(
                "hub.mode"
            )
            == "subscribe"

            and request.args.get(
                "hub.verify_token"
            )
            == VERIFY_TOKEN
        ):
            return request.args.get(
                "hub.challenge"
            ), 200

        return "Forbidden", 403

    data = request.get_json(
        silent=True
    ) or {}

    try:
        entries = data.get(
            "entry"
        ) or []

        if not entries:
            return jsonify(
                {
                    "status":
                        "success"
                }
            ), 200

        changes = (
            entries[0]
            .get(
                "changes"
            )
            or []
        )

        if not changes:
            return jsonify(
                {
                    "status":
                        "success"
                }
            ), 200

        value = (
            changes[0]
            .get(
                "value"
            )
            or {}
        )

        messages = value.get(
            "messages"
        ) or []

        if messages:
            process_message(
                messages[0]
            )

    except Exception as exc:
        print(
            "Error processing Meta webhook:",
            exc,
        )

    return jsonify(
        {
            "status":
                "success"
        }
    ), 200


# ============================================================
# RAZORPAY WEBHOOK
# ============================================================

@app.route(
    "/razorpay-webhook",
    methods=["POST"],
)
def razorpay_webhook():
    """
    Handles successful Razorpay Payment Link payments.

    Existing Project B flow is preserved:

    Pending -> Paid
    clear WhatsApp session
    send payment confirmation

    Inventory is now reduced ONLY when that menu item
    has track_inventory = TRUE.
    """

    data = request.get_json(
        silent=True
    ) or {}

    conn = None

    try:
        if (
            data.get(
                "event"
            )
            != "payment_link.paid"
        ):
            return jsonify(
                {
                    "status": "ok"
                }
            ), 200

        payment_link_entity = (
            data
            .get(
                "payload",
                {},
            )
            .get(
                "payment_link",
                {},
            )
            .get(
                "entity",
                {},
            )
        )

        notes = (
            payment_link_entity
            .get(
                "notes"
            )
            or {}
        )

        order_id = notes.get(
            "order_id"
        )

        sender_phone = notes.get(
            "phone_number"
        )

        if not order_id:
            print(
                "Razorpay webhook missing order_id"
            )

            return jsonify(
                {
                    "status": "ok"
                }
            ), 200

        conn = get_db_connection()

        cur = conn.cursor(
            cursor_factory=
                RealDictCursor
        )

        # ====================================================
        # IDEMPOTENT STATUS UPDATE
        # ====================================================

        cur.execute(
            """
            UPDATE orders

            SET
                status = 'Paid',
                paid_at = NOW(),
                updated_at = NOW()

            WHERE
                order_id = %s
                AND status = 'Pending'

            RETURNING cart_items
            """,
            (
                order_id,
            ),
        )

        order = cur.fetchone()

        # Already processed or order does not exist.
        if not order:
            conn.commit()

            return jsonify(
                {
                    "status": "ok"
                }
            ), 200

        cart = normalize_cart(
            order.get(
                "cart_items"
            )
        )

        # ====================================================
        # OPTIONAL INVENTORY DECREMENT
        # ====================================================

        for cart_item in cart:
            if not cart_item_tracks_inventory(
                cur,
                cart_item,
            ):
                continue

            item_id = cart_item.get(
                "id"
            )

            qty = int(
                cart_item.get(
                    "qty",
                    0,
                )
            )

            if (
                not item_id
                or qty <= 0
            ):
                continue

            cur.execute(
                """
                UPDATE menu

                SET
                    inventory = GREATEST(
                        inventory - %s,
                        0
                    ),
                    updated_at = NOW()

                WHERE
                    id = %s
                    AND track_inventory = TRUE
                """,
                (
                    qty,
                    item_id,
                ),
            )

        # ====================================================
        # CLEAR CUSTOMER SESSION
        # ====================================================

        if sender_phone:
            cur.execute(
                """
                DELETE FROM sessions
                WHERE phone_number = %s
                """,
                (
                    sender_phone,
                ),
            )

        conn.commit()

        # ====================================================
        # PAYMENT SUCCESS MESSAGE
        # ====================================================

        if sender_phone:
            send_reply(
                sender_phone,
                (
                    "✅ *Payment Successful!*\n\n"
                    f"Your order ({order_id}) has been placed "
                    "and is being prepared.\n\n"
                    "Thank you for choosing "
                    "Watave's Biriyani Point!"
                ),
            )

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        print(
            "Error processing Razorpay webhook:",
            exc,
        )

    finally:
        if conn is not None:
            conn.close()

    return jsonify(
        {
            "status": "ok"
        }
    ), 200


# ============================================================
# LEGACY ADMIN API
#
# These routes are retained because they existed in Project B.
# The new dashboard uses /api/v1 instead.
# ============================================================

@app.route(
    "/api/admin/<path:_path>",
    methods=["OPTIONS"],
)
def admin_options(_path):
    return "", 204


@app.get(
    "/api/admin/dashboard"
)
def admin_dashboard():
    conn = get_db_connection()

    try:
        cur = conn.cursor(
            cursor_factory=
                RealDictCursor
        )

        cur.execute(
            """
            SELECT
                COALESCE(
                    SUM(total_amount)
                    FILTER (
                        WHERE status IN (
                            'Paid',
                            'Preparation',
                            'Ready',
                            'Collected'
                        )
                        AND COALESCE(
                            paid_at,
                            created_at
                        )::date = CURRENT_DATE
                    ),
                    0
                )::integer AS today_revenue,

                COUNT(*)
                FILTER (
                    WHERE status IN (
                        'Paid',
                        'Preparation',
                        'Ready',
                        'Collected'
                    )
                    AND COALESCE(
                        paid_at,
                        created_at
                    )::date = CURRENT_DATE
                ) AS today_orders,

                COUNT(*)
                FILTER (
                    WHERE status IN (
                        'Paid',
                        'Preparation',
                        'Ready'
                    )
                ) AS active_orders,

                COUNT(*)
                FILTER (
                    WHERE status = 'Collected'
                    AND COALESCE(
                        completed_at,
                        updated_at
                    )::date = CURRENT_DATE
                ) AS completed_today,

                COALESCE(
                    AVG(total_amount)
                    FILTER (
                        WHERE status IN (
                            'Paid',
                            'Preparation',
                            'Ready',
                            'Collected'
                        )
                        AND COALESCE(
                            paid_at,
                            created_at
                        )::date = CURRENT_DATE
                    ),
                    0
                )::integer AS average_order_value

            FROM orders
            """
        )

        summary = dict(
            cur.fetchone()
        )

        cur.execute(
            """
            SELECT
                d.day::date AS day,
                TO_CHAR(
                    d.day,
                    'Dy'
                ) AS label,

                COALESCE(
                    SUM(
                        o.total_amount
                    ),
                    0
                )::integer AS revenue

            FROM generate_series(
                CURRENT_DATE - INTERVAL '6 days',
                CURRENT_DATE,
                INTERVAL '1 day'
            ) d(day)

            LEFT JOIN orders o
                ON COALESCE(
                    o.paid_at,
                    o.created_at
                )::date = d.day::date

                AND o.status IN (
                    'Paid',
                    'Preparation',
                    'Ready',
                    'Collected'
                )

            GROUP BY d.day

            ORDER BY d.day
            """
        )

        summary[
            "sales_last_7_days"
        ] = cur.fetchall()

        return jsonify(
            summary
        )

    finally:
        conn.close()


@app.get(
    "/api/admin/orders"
)
def admin_orders():
    include_history = (
        request.args.get(
            "history",
            "false",
        ).lower()
        == "true"
    )

    conn = get_db_connection()

    try:
        cur = conn.cursor(
            cursor_factory=
                RealDictCursor
        )

        if include_history:
            cur.execute(
                """
                SELECT *
                FROM orders
                ORDER BY created_at DESC
                LIMIT 250
                """
            )

        else:
            cur.execute(
                """
                SELECT *
                FROM orders

                WHERE status IN (
                    'Paid',
                    'Preparation',
                    'Ready'
                )

                ORDER BY created_at ASC
                """
            )

        return jsonify(
            cur.fetchall()
        )

    finally:
        conn.close()


@app.patch(
    "/api/admin/orders/<order_id>/status"
)
def admin_update_order_status(
    order_id,
):
    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    new_status = body.get(
        "status"
    )

    allowed_next = {
        "Paid":
            "Preparation",

        "Preparation":
            "Ready",

        "Ready":
            "Collected",
    }

    if new_status not in (
        allowed_next.values()
    ):
        return jsonify(
            {
                "error":
                    "Invalid order status"
            }
        ), 400

    conn = get_db_connection()

    try:
        cur = conn.cursor(
            cursor_factory=
                RealDictCursor
        )

        cur.execute(
            """
            SELECT status
            FROM orders

            WHERE order_id = %s

            FOR UPDATE
            """,
            (
                order_id,
            ),
        )

        order = cur.fetchone()

        if not order:
            return jsonify(
                {
                    "error":
                        "Order not found"
                }
            ), 404

        if (
            allowed_next.get(
                order[
                    "status"
                ]
            )
            != new_status
        ):
            return jsonify(
                {
                    "error":
                        (
                            f"Cannot move "
                            f"{order['status']} "
                            f"to {new_status}"
                        )
                }
            ), 409

        cur.execute(
            """
            UPDATE orders

            SET
                status = %s,
                updated_at = NOW(),

                completed_at =
                    CASE
                        WHEN %s = 'Collected'
                        THEN NOW()
                        ELSE completed_at
                    END

            WHERE order_id = %s

            RETURNING *
            """,
            (
                new_status,
                new_status,
                order_id,
            ),
        )

        updated = cur.fetchone()

        conn.commit()

        return jsonify(
            updated
        )

    finally:
        conn.close()


# ============================================================
# LEGACY ADMIN MENU
# ============================================================

def parse_dish_payload(
    partial=False,
):
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    result = {}

    if (
        not partial
        or "name" in data
    ):
        name = str(
            data.get(
                "name",
                "",
            )
        ).strip()

        if not name:
            raise ValueError(
                "Dish name is required"
            )

        result[
            "name"
        ] = name

    for field in (
        "price",
        "inventory",
    ):
        if (
            not partial
            or field in data
        ):
            value = int(
                data.get(
                    field,
                    0,
                )
            )

            if value < 0:
                raise ValueError(
                    f"{field} cannot be negative"
                )

            result[
                field
            ] = value

    if (
        not partial
        or "track_inventory" in data
    ):
        result[
            "track_inventory"
        ] = bool(
            data.get(
                "track_inventory",
                False,
            )
        )

    if "is_active" in data:
        result[
            "is_active"
        ] = bool(
            data[
                "is_active"
            ]
        )

    return result


@app.route(
    "/api/admin/menu",
    methods=[
        "GET",
        "POST",
    ],
)
def admin_menu():
    conn = get_db_connection()

    try:
        cur = conn.cursor(
            cursor_factory=
                RealDictCursor
        )

        if request.method == "GET":
            cur.execute(
                """
                SELECT *
                FROM menu

                ORDER BY
                    is_active DESC,
                    name
                """
            )

            return jsonify(
                cur.fetchall()
            )

        try:
            dish = (
                parse_dish_payload()
            )

        except (
            ValueError,
            TypeError,
        ) as exc:
            return jsonify(
                {
                    "error":
                        str(exc)
                }
            ), 400

        cur.execute(
            """
            INSERT INTO menu (
                name,
                price,
                inventory,
                track_inventory
            )

            VALUES (
                %s,
                %s,
                %s,
                %s
            )

            RETURNING *
            """,
            (
                dish[
                    "name"
                ],

                dish[
                    "price"
                ],

                dish[
                    "inventory"
                ],

                dish[
                    "track_inventory"
                ],
            ),
        )

        created = cur.fetchone()

        conn.commit()

        return jsonify(
            created
        ), 201

    finally:
        conn.close()


@app.route(
    "/api/admin/menu/<int:item_id>",
    methods=[
        "PATCH",
        "DELETE",
    ],
)
def admin_menu_item(
    item_id,
):
    conn = get_db_connection()

    try:
        cur = conn.cursor(
            cursor_factory=
                RealDictCursor
        )

        if (
            request.method
            == "DELETE"
        ):
            cur.execute(
                """
                UPDATE menu

                SET
                    is_active = FALSE,
                    updated_at = NOW()

                WHERE id = %s

                RETURNING id
                """,
                (
                    item_id,
                ),
            )

            if not cur.fetchone():
                return jsonify(
                    {
                        "error":
                            "Dish not found"
                    }
                ), 404

            conn.commit()

            return jsonify(
                {
                    "status":
                        "deleted"
                }
            )

        try:
            dish = (
                parse_dish_payload(
                    partial=True
                )
            )

        except (
            ValueError,
            TypeError,
        ) as exc:
            return jsonify(
                {
                    "error":
                        str(exc)
                }
            ), 400

        if not dish:
            return jsonify(
                {
                    "error":
                        "No fields to update"
                }
            ), 400

        columns = list(
            dish.keys()
        )

        assignments = ", ".join(
            f"{column} = %s"
            for column
            in columns
        )

        values = [
            dish[
                column
            ]
            for column
            in columns
        ]

        cur.execute(
            f"""
            UPDATE menu

            SET
                {assignments},
                updated_at = NOW()

            WHERE id = %s

            RETURNING *
            """,
            (
                *values,
                item_id,
            ),
        )

        updated = cur.fetchone()

        if not updated:
            return jsonify(
                {
                    "error":
                        "Dish not found"
                }
            ), 404

        conn.commit()

        return jsonify(
            updated
        )

    finally:
        conn.close()


# ============================================================
# CART HELPERS
# ============================================================

def normalize_cart(
    value,
):
    if not value:
        return []

    if isinstance(
        value,
        list,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        try:
            parsed = json.loads(
                value
            )

            if isinstance(
                parsed,
                list,
            ):
                return parsed

        except json.JSONDecodeError:
            return []

    return []


def cart_item_tracks_inventory(
    cur,
    cart_item,
):
    """
    New carts store track_inventory in the cart snapshot.

    Older Project B orders do not have that key, so for old
    carts we fall back to the current menu row.
    """

    if (
        "track_inventory"
        in cart_item
    ):
        return bool(
            cart_item[
                "track_inventory"
            ]
        )

    item_id = cart_item.get(
        "id"
    )

    if not item_id:
        return False

    cur.execute(
        """
        SELECT track_inventory
        FROM menu
        WHERE id = %s
        """,
        (
            item_id,
        ),
    )

    row = cur.fetchone()

    if not row:
        return False

    return bool(
        row[
            "track_inventory"
        ]
    )


# ============================================================
# WHATSAPP ORDER STATE MACHINE
# ============================================================

def process_message(
    message,
):
    sender_phone = message[
        "from"
    ]

    msg_type = message.get(
        "type"
    )

    incoming_text = ""
    interactive_id = ""

    if msg_type == "text":
        incoming_text = (
            message[
                "text"
            ][
                "body"
            ]
            .strip()
            .lower()
        )

    elif msg_type == "interactive":
        interactive = (
            message[
                "interactive"
            ]
        )

        if (
            interactive[
                "type"
            ]
            == "button_reply"
        ):
            interactive_id = (
                interactive[
                    "button_reply"
                ][
                    "id"
                ]
            )

        elif (
            interactive[
                "type"
            ]
            == "list_reply"
        ):
            interactive_id = (
                interactive[
                    "list_reply"
                ][
                    "id"
                ]
            )

    conn = get_db_connection()

    cur = conn.cursor(
        cursor_factory=
            RealDictCursor
    )

    try:
        cur.execute(
            """
            SELECT *
            FROM sessions
            WHERE phone_number = %s
            """,
            (
                sender_phone,
            ),
        )

        session = cur.fetchone()

        # ====================================================
        # START / RESTART
        # ====================================================

        start_words = {
            "hi",
            "hello",
            "start",
            "restart",
        }

        is_start_message = (
            incoming_text
            in start_words
        )

        if is_start_message:
            if session:
                cur.execute(
                    """
                    DELETE FROM sessions
                    WHERE phone_number = %s
                    """,
                    (
                        sender_phone,
                    ),
                )

                conn.commit()

            session = None

        # ====================================================
        # NEW SESSION
        # ====================================================

        if not session:
            if not is_start_message:
                send_reply(
                    sender_phone,
                    (
                        "Welcome to Watave's "
                        "Biriyani Point! 🍛\n\n"
                        "Say *Hi* to place your order."
                    ),
                )

                return

            cur.execute(
                """
                INSERT INTO users (
                    phone_number
                )

                VALUES (%s)

                ON CONFLICT DO NOTHING
                """,
                (
                    sender_phone,
                ),
            )

            cur.execute(
                """
                INSERT INTO sessions (
                    phone_number,
                    step
                )

                VALUES (
                    %s,
                    %s
                )

                RETURNING *
                """,
                (
                    sender_phone,
                    "CHOOSE_DINING",
                ),
            )

            conn.commit()

            send_button_message(
                sender_phone,
                (
                    "How would you like "
                    "to order?"
                ),
                [
                    {
                        "id":
                            "takeaway",

                        "title":
                            "🥡 Takeaway",
                    },
                    {
                        "id":
                            "dine_in",

                        "title":
                            "🍽️ Dine-in",
                    },
                ],
            )

            return

        step = session[
            "step"
        ]

        # ====================================================
        # STEP 1 — DINING TYPE
        # ====================================================

        if (
            step
            == "CHOOSE_DINING"
        ):
            if (
                interactive_id
                == "takeaway"
            ):
                cur.execute(
                    """
                    UPDATE sessions

                    SET
                        order_type = 'Takeaway',
                        step = 'CHOOSE_CATEGORY'

                    WHERE phone_number = %s
                    """,
                    (
                        sender_phone,
                    ),
                )

                show_categories(
                    sender_phone
                )

            elif (
                interactive_id
                == "dine_in"
            ):
                send_reply(
                    sender_phone,
                    (
                        "Please enter your "
                        "table number:"
                    ),
                )

                cur.execute(
                    """
                    UPDATE sessions

                    SET
                        order_type = 'Dine-in',
                        step = 'ENTER_TABLE'

                    WHERE phone_number = %s
                    """,
                    (
                        sender_phone,
                    ),
                )

            else:
                send_reply(
                    sender_phone,
                    (
                        "Please tap Takeaway "
                        "or Dine-in."
                    ),
                )

        # ====================================================
        # STEP 2 — TABLE
        # ====================================================

        elif (
            step
            == "ENTER_TABLE"
        ):
            if msg_type == "text":
                table_number = (
                    message[
                        "text"
                    ][
                        "body"
                    ]
                    .strip()
                )

                if not table_number:
                    send_reply(
                        sender_phone,
                        (
                            "Please enter a "
                            "valid table number."
                        ),
                    )

                    return

                cur.execute(
                    """
                    UPDATE sessions

                    SET
                        table_number = %s,
                        step = 'CHOOSE_CATEGORY'

                    WHERE phone_number = %s
                    """,
                    (
                        table_number,
                        sender_phone,
                    ),
                )

                show_categories(
                    sender_phone
                )

        # ====================================================
        # STEP 3 — CATEGORY
        # ====================================================

        elif (
            step
            == "CHOOSE_CATEGORY"
        ):
            category_map = {
                "cat_biryani":
                    (
                        "biryani",
                        "CHOOSE_ITEM_BIRYANI",
                    ),

                "cat_65_weight":
                    (
                        "chicken65_weight",
                        "CHOOSE_ITEM_65_WEIGHT",
                    ),

                "cat_65_packs":
                    (
                        "chicken65_packs",
                        "CHOOSE_ITEM_65_PACK",
                    ),
            }

            selected = (
                category_map.get(
                    interactive_id
                )
            )

            if not selected:
                send_reply(
                    sender_phone,
                    (
                        "Please choose one "
                        "of the menu categories."
                    ),
                )

                show_categories(
                    sender_phone
                )

            else:
                (
                    category_key,
                    next_step,
                ) = selected

                cur.execute(
                    """
                    UPDATE sessions

                    SET step = %s

                    WHERE phone_number = %s
                    """,
                    (
                        next_step,
                        sender_phone,
                    ),
                )

                show_category_menu(
                    sender_phone,
                    cur,
                    category_key,
                )

        # ====================================================
        # STEP 4 — ITEM
        # ====================================================

        elif step in {
            "CHOOSE_ITEM_BIRYANI",
            "CHOOSE_ITEM_65_WEIGHT",
            "CHOOSE_ITEM_65_PACK",
        }:
            if (
                interactive_id
                == "back_categories"
            ):
                cur.execute(
                    """
                    UPDATE sessions

                    SET step = 'CHOOSE_CATEGORY'

                    WHERE phone_number = %s
                    """,
                    (
                        sender_phone,
                    ),
                )

                show_categories(
                    sender_phone
                )

            elif interactive_id.startswith(
                "item_"
            ):
                try:
                    item_id = int(
                        interactive_id[
                            len(
                                "item_"
                            ):
                        ]
                    )

                except ValueError:
                    send_reply(
                        sender_phone,
                        (
                            "Please choose a "
                            "valid menu item."
                        ),
                    )

                    return

                cur.execute(
                    """
                    SELECT *
                    FROM menu

                    WHERE
                        id = %s
                        AND is_active = TRUE

                    LIMIT 1
                    """,
                    (
                        item_id,
                    ),
                )

                item = cur.fetchone()

                if not item:
                    send_reply(
                        sender_phone,
                        (
                            "That item is no "
                            "longer available."
                        ),
                    )

                    cur.execute(
                        """
                        UPDATE sessions
                        SET step = 'CHOOSE_CATEGORY'
                        WHERE phone_number = %s
                        """,
                        (
                            sender_phone,
                        ),
                    )

                    show_categories(
                        sender_phone
                    )

                    return

                if (
                    item[
                        "track_inventory"
                    ]
                    and item[
                        "inventory"
                    ] <= 0
                ):
                    send_reply(
                        sender_phone,
                        (
                            f"Sorry, {item['name']} "
                            "is currently sold out."
                        ),
                    )

                    return

                cur.execute(
                    """
                    UPDATE sessions

                    SET
                        temp_item_id = %s,
                        step = 'CHOOSE_QUANTITY'

                    WHERE phone_number = %s
                    """,
                    (
                        item_id,
                        sender_phone,
                    ),
                )

                send_reply(
                    sender_phone,
                    (
                        f"*{item['name']}*\n"
                        f"Price: ₹{item['price']}\n\n"
                        "How many would you like?\n"
                        "Please type a quantity."
                    ),
                )

            else:
                send_reply(
                    sender_phone,
                    (
                        "Please select an item "
                        "from the menu list."
                    ),
                )

        # ====================================================
        # STEP 5 — QUANTITY
        # ====================================================

        elif (
            step
            == "CHOOSE_QUANTITY"
        ):
            if msg_type != "text":
                send_reply(
                    sender_phone,
                    (
                        "Please type the quantity "
                        "as a number."
                    ),
                )

                return

            try:
                qty = int(
                    incoming_text
                )

                if qty <= 0:
                    raise ValueError

            except ValueError:
                send_reply(
                    sender_phone,
                    (
                        "Please enter a valid "
                        "quantity such as 1, 2 or 3."
                    ),
                )

                return

            item_id = session[
                "temp_item_id"
            ]

            cur.execute(
                """
                SELECT *
                FROM menu

                WHERE
                    id = %s
                    AND is_active = TRUE

                LIMIT 1
                """,
                (
                    item_id,
                ),
            )

            item = cur.fetchone()

            if not item:
                send_reply(
                    sender_phone,
                    (
                        "That menu item is no "
                        "longer available."
                    ),
                )

                cur.execute(
                    """
                    UPDATE sessions

                    SET step = 'CHOOSE_CATEGORY'

                    WHERE phone_number = %s
                    """,
                    (
                        sender_phone,
                    ),
                )

                show_categories(
                    sender_phone
                )

                return

            # =================================================
            # INVENTORY CHECK ONLY WHEN TRACKING IS ENABLED
            # =================================================

            if item[
                "track_inventory"
            ]:
                available_stock = int(
                    item[
                        "inventory"
                    ]
                )

                if (
                    available_stock
                    <= 0
                ):
                    send_reply(
                        sender_phone,
                        (
                            f"Sorry, {item['name']} "
                            "is currently sold out."
                        ),
                    )

                    return

                if qty > available_stock:
                    send_reply(
                        sender_phone,
                        (
                            "Sorry, we currently have only "
                            f"{available_stock} of "
                            f"{item['name']} available.\n\n"
                            "Please enter a smaller quantity."
                        ),
                    )

                    return

            cart = normalize_cart(
                session.get(
                    "cart"
                )
            )

            cart.append(
                {
                    "id":
                        item[
                            "id"
                        ],

                    "name":
                        item[
                            "name"
                        ],

                    "price":
                        item[
                            "price"
                        ],

                    "qty":
                        qty,

                    "track_inventory":
                        bool(
                            item[
                                "track_inventory"
                            ]
                        ),
                }
            )

            cur.execute(
                """
                UPDATE sessions

                SET
                    cart = %s,
                    step = 'CART_OPTIONS'

                WHERE phone_number = %s
                """,
                (
                    json.dumps(
                        cart
                    ),
                    sender_phone,
                ),
            )

            total = sum(
                int(
                    cart_item[
                        "price"
                    ]
                )
                * int(
                    cart_item[
                        "qty"
                    ]
                )

                for cart_item
                in cart
            )

            summary = (
                "🛒 *Cart Preview*\n\n"
            )

            for cart_item in cart:
                line_total = (
                    int(
                        cart_item[
                            "price"
                        ]
                    )
                    * int(
                        cart_item[
                            "qty"
                        ]
                    )
                )

                summary += (
                    f"• {cart_item['qty']}x "
                    f"{cart_item['name']} "
                    f"(₹{line_total})\n"
                )

            summary += (
                f"\n*Total: ₹{total}*"
            )

            send_button_message(
                sender_phone,
                summary,
                [
                    {
                        "id":
                            "add_item",

                        "title":
                            "➕ Add Item",
                    },
                    {
                        "id":
                            "checkout",

                        "title":
                            "💳 Checkout",
                    },
                    {
                        "id":
                            "cancel",

                        "title":
                            "❌ Cancel",
                    },
                ],
            )

        # ====================================================
        # STEP 6 — CART
        # ====================================================

        elif (
            step
            == "CART_OPTIONS"
        ):
            if (
                interactive_id
                == "add_item"
            ):
                cur.execute(
                    """
                    UPDATE sessions

                    SET step = 'CHOOSE_CATEGORY'

                    WHERE phone_number = %s
                    """,
                    (
                        sender_phone,
                    ),
                )

                show_categories(
                    sender_phone
                )

            elif (
                interactive_id
                == "cancel"
            ):
                cur.execute(
                    """
                    DELETE FROM sessions
                    WHERE phone_number = %s
                    """,
                    (
                        sender_phone,
                    ),
                )

                send_reply(
                    sender_phone,
                    (
                        "Order cancelled.\n\n"
                        "Say *Hi* whenever "
                        "you are hungry again!"
                    ),
                )

            elif (
                interactive_id
                == "checkout"
            ):
                cart = normalize_cart(
                    session.get(
                        "cart"
                    )
                )

                if not cart:
                    send_reply(
                        sender_phone,
                        (
                            "Your cart is empty."
                        ),
                    )

                    return

                total = sum(
                    int(
                        cart_item[
                            "price"
                        ]
                    )
                    * int(
                        cart_item[
                            "qty"
                        ]
                    )

                    for cart_item
                    in cart
                )

                order_id = (
                    "ORD-"
                    + uuid.uuid4()
                    .hex[
                        :6
                    ]
                    .upper()
                )

                # =================================================
                # PROJECT B ORDER STRUCTURE — PRESERVED
                # =================================================

                cur.execute(
                    """
                    INSERT INTO orders (
                        order_id,
                        phone_number,
                        order_type,
                        table_number,
                        total_amount,
                        cart_items,
                        status
                    )

                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'Pending'
                    )
                    """,
                    (
                        order_id,

                        sender_phone,

                        session[
                            "order_type"
                        ],

                        session[
                            "table_number"
                        ],

                        total,

                        json.dumps(
                            cart
                        ),
                    ),
                )

                # =================================================
                # RAZORPAY PAYMENT LINK — PRESERVED
                # =================================================

                payment_link_data = {
                    "amount":
                        total * 100,

                    "currency":
                        "INR",

                    "description":
                        "Watave's Biriyani Point",

                    "customer": {
                        "contact":
                            f"+{sender_phone}"
                    },

                    "notes": {
                        "order_id":
                            order_id,

                        "phone_number":
                            sender_phone,
                    },
                }

                payment_link = (
                    rzp_client
                    .payment_link
                    .create(
                        payment_link_data
                    )
                )

                payment_url = (
                    payment_link[
                        "short_url"
                    ]
                )

                send_reply(
                    sender_phone,
                    (
                        "🧾 *Final Checkout*\n\n"
                        f"Order: {order_id}\n"
                        f"Total Amount: ₹{total}\n\n"
                        "Please use the payment "
                        "link below to confirm your order:\n\n"
                        f"{payment_url}"
                    ),
                )

                cur.execute(
                    """
                    UPDATE sessions

                    SET step = 'AWAITING_PAYMENT'

                    WHERE phone_number = %s
                    """,
                    (
                        sender_phone,
                    ),
                )

        # ====================================================
        # WAITING FOR PAYMENT
        # ====================================================

        elif (
            step
            == "AWAITING_PAYMENT"
        ):
            send_reply(
                sender_phone,
                (
                    "Payment confirmation is "
                    "still pending.\n\n"
                    "Complete the payment link, "
                    "or send *Restart* to begin again."
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# MENU CATEGORIES
# ============================================================

def show_categories(
    phone_number,
):
    send_button_message(
        phone_number,
        "🍽️ *Choose a Menu Category*",
        [
            {
                "id":
                    "cat_biryani",

                "title":
                    "🍚 Biryani",
            },
            {
                "id":
                    "cat_65_weight",

                "title":
                    "🍗 Chicken 65 Weight",
            },
            {
                "id":
                    "cat_65_packs",

                "title":
                    "🍗 Chicken 65 Packs",
            },
        ],
    )


def show_category_menu(
    phone_number,
    cur,
    category,
):
    if category == "biryani":
        title = "Biryani"

        cur.execute(
            """
            SELECT *
            FROM menu

            WHERE
                is_active = TRUE

                AND (
                    track_inventory = FALSE
                    OR inventory > 0
                )

                AND category = 'BIRYANI'

            ORDER BY name
            """
        )

    elif (
        category
        == "chicken65_weight"
    ):
        title = "Chicken 65 - Weight"

        cur.execute(
            """
            SELECT *
            FROM menu

            WHERE
                is_active = TRUE

                AND (
                    track_inventory = FALSE
                    OR inventory > 0
                )

                AND category = 'CHICKEN_65_WEIGHT'

            ORDER BY
                price,
                name
            """
        )

    elif (
        category
        == "chicken65_packs"
    ):
        title = "Chicken 65 - Packs"

        cur.execute(
            """
            SELECT *
            FROM menu

            WHERE
                is_active = TRUE

                AND (
                    track_inventory = FALSE
                    OR inventory > 0
                )

                AND category = 'CHICKEN_65_PACKS'

            ORDER BY
                price,
                name
            """
        )

    else:
        send_reply(
            phone_number,
            (
                "Invalid menu category."
            ),
        )

        return

    items = cur.fetchall()

    if not items:
        cur.execute(
            """
            UPDATE sessions
            SET step = 'CHOOSE_CATEGORY'
            WHERE phone_number = %s
            """,
            (
                phone_number,
            ),
        )

        send_reply(
            phone_number,
            (
                "Sorry, there are currently "
                f"no available items in {title}."
            ),
        )

        show_categories(
            phone_number
        )

        return

    rows = []

    for item in items:
        description = (
            f"₹{item['price']}"
        )

        if item[
            "track_inventory"
        ]:
            description += (
                f" • {item['inventory']} left"
            )

        rows.append(
            {
                "id":
                    f"item_{item['id']}",

                "title":
                    whatsapp_item_title(
                        item[
                            "name"
                        ]
                    ),

                "description":
                    description,
            }
        )

    # Current real menu categories contain fewer than 10 rows.
    rows.append(
        {
            "id":
                "back_categories",

            "title":
                "← Back",

            "description":
                "Choose another category",
        }
    )

    send_list_message(
        phone_number,
        f"Choose an item from *{title}*:",
        "View Items",
        title,
        rows,
    )


def whatsapp_item_title(
    name,
):
    title = name

    lower_name = (
        name.lower()
    )

    if (
        "dum biryani"
        in lower_name
    ):
        title = (
            name
            .replace(
                " Dum Biryani",
                "",
            )
        )

    elif lower_name.startswith(
        "chicken 65"
    ):
        title = (
            name
            .replace(
                "Chicken 65 - ",
                "",
            )
        )

    # Keep interactive list titles short.
    return title[
        :24
    ]


# ============================================================
# WHATSAPP SEND HELPERS
# ============================================================

def whatsapp_api_url():
    return (
        "https://graph.facebook.com/"
        f"{WHATSAPP_GRAPH_VERSION}/"
        f"{PHONE_NUMBER_ID}/messages"
    )


def send_whatsapp_payload(
    payload,
):
    try:
        response = requests.post(
            whatsapp_api_url(),

            headers={
                "Authorization":
                    f"Bearer {ACCESS_TOKEN}",

                "Content-Type":
                    "application/json",
            },

            json=payload,

            timeout=20,
        )

        if not response.ok:
            print(
                "WhatsApp API error:",
                response.status_code,
                response.text,
            )

    except requests.RequestException as exc:
        print(
            "WhatsApp request failed:",
            exc,
        )


def send_button_message(
    phone_number,
    text_message,
    buttons,
):
    payload = {
        "messaging_product":
            "whatsapp",

        "to":
            phone_number,

        "type":
            "interactive",

        "interactive": {
            "type":
                "button",

            "body": {
                "text":
                    text_message
            },

            "action": {
                "buttons": [
                    {
                        "type":
                            "reply",

                        "reply": {
                            "id":
                                button[
                                    "id"
                                ],

                            "title":
                                button[
                                    "title"
                                ],
                        },
                    }

                    for button
                    in buttons
                ]
            },
        },
    }

    send_whatsapp_payload(
        payload
    )


def send_list_message(
    phone_number,
    text_message,
    button_title,
    section_title,
    rows,
):
    payload = {
        "messaging_product":
            "whatsapp",

        "to":
            phone_number,

        "type":
            "interactive",

        "interactive": {
            "type":
                "list",

            "body": {
                "text":
                    text_message
            },

            "action": {
                "button":
                    button_title,

                "sections": [
                    {
                        "title":
                            section_title,

                        "rows":
                            rows,
                    }
                ],
            },
        },
    }

    send_whatsapp_payload(
        payload
    )


def send_reply(
    phone_number,
    text_message,
):
    payload = {
        "messaging_product":
            "whatsapp",

        "to":
            phone_number,

        "type":
            "text",

        "text": {
            "body":
                text_message
        },
    }

    send_whatsapp_payload(
        payload
    )


if __name__ == "__main__":
    app.run(
        port=5000,
        debug=True,
    )