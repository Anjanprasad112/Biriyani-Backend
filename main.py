import os
import requests
import razorpay
import uuid
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- SECRETS & CONFIG ---
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# --- DATABASE CONNECTION ---
def get_db_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

# Main Route
@app.get("/")
def home():
    return {"status": "ok"}


# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200


# --- WEBHOOK ROUTES ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Forbidden', 403

    if request.method == 'POST':
        data = request.get_json()
        try:
            if data.get('entry') and data['entry'][0].get('changes'):
                change = data['entry'][0]['changes'][0]['value']
                if 'messages' in change:
                    message = change['messages'][0]
                    process_message(message)
        except Exception as e:
            print(f"Error processing Meta webhook: {e}")
        return jsonify({"status": "success"}), 200

@app.route('/razorpay-webhook', methods=['POST'])
def razorpay_webhook():
    """Handles successful payments, stores payment details, and decrements inventory."""
    data = request.get_json()
    try:
        if data.get('event') == 'payment_link.paid':
            # Extract the entities from the Razorpay payload
            payment_link_entity = data['payload']['payment_link']['entity']
            payment_entity = data['payload']['payment']['entity']
            
            # Extract our custom notes
            notes = payment_link_entity.get('notes', {})
            order_id = notes.get('order_id')
            sender_phone = notes.get('phone_number')
            
            # Extract specific payment details
            payment_id = payment_entity.get('id')
            amount_paid = int(payment_entity.get('amount') / 100) # Convert from paise back to Rupees
            
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # 1. Update Order Status
            cur.execute("UPDATE orders SET status = 'Paid' WHERE order_id = %s RETURNING cart_items", (order_id,))
            order = cur.fetchone()
            
            # 2. Store the exact Payment Details in the database
            cur.execute("""
                INSERT INTO payments (payment_id, order_id, phone_number, amount)
                VALUES (%s, %s, %s, %s)
            """, (payment_id, order_id, sender_phone, amount_paid))
            
            # 3. Decrement Inventory
            if order:
                cart = order['cart_items']
                for item in cart:
                    cur.execute("UPDATE menu SET inventory = inventory - %s WHERE id = %s", (item['qty'], item['id']))
            
            # 4. Clear session and notify user
            cur.execute("DELETE FROM sessions WHERE phone_number = %s", (sender_phone,))
            conn.commit()
            conn.close()
            
            # Include the transaction ID and amount in the customer receipt
            receipt_msg = (
                f"✅ *Payment Successful!*\n\n"
                f"Your order ({order_id}) has been placed and is being prepared.\n\n"
                f"🧾 *Transaction Details:*\n"
                f"Amount Paid: ₹{amount_paid}\n"
                f"Payment ID: {payment_id}\n\n"
                f"Thank you for choosing Watave's Biriyani Point!"
            )
            send_reply(sender_phone, receipt_msg)
            
    except Exception as e:
        print(f"Error processing Razorpay webhook: {e}")
    return jsonify({"status": "ok"}), 200

# --- BOT LOGIC & STATE MACHINE ---
def process_message(message):
    sender_phone = message['from']
    msg_type = message.get('type')
    
    incoming_text = ""
    interactive_id = ""
    
    if msg_type == 'text':
        incoming_text = message['text']['body'].strip().lower()
    elif msg_type == 'interactive':
        inter = message['interactive']
        if inter['type'] == 'button_reply':
            interactive_id = inter['button_reply']['id']
        elif inter['type'] == 'list_reply':
            interactive_id = inter['list_reply']['id']

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM sessions WHERE phone_number = %s", (sender_phone,))
    session = cur.fetchone()

    # Reset trigger
    if incoming_text == 'hi':
        if session:
            cur.execute("DELETE FROM sessions WHERE phone_number = %s", (sender_phone,))
            conn.commit()
        session = None

    # Initialize new session
    if not session:
        if incoming_text != 'hi':
            send_reply(sender_phone, "Welcome to Watave's Biriyani Point! 🍛\nSay 'Hi' to place your order.")
            conn.close()
            return
        else:
            # Register user in DB if they don't exist
            cur.execute("INSERT INTO users (phone_number) VALUES (%s) ON CONFLICT DO NOTHING", (sender_phone,))
            cur.execute("INSERT INTO sessions (phone_number, step) VALUES (%s, %s) RETURNING *", (sender_phone, 'CHOOSE_DINING'))
            session = cur.fetchone()
            conn.commit()
            send_button_message(sender_phone, "Are you ordering for Takeaway or Dine-in?", [
                {"id": "takeaway", "title": "🥡 Takeaway"},
                {"id": "dine_in", "title": "🍽️ Dine-in"}
            ])
            conn.close()
            return

    step = session['step']

    # --- STATE 1: CHOOSE DINING ---
    if step == 'CHOOSE_DINING':
        if interactive_id == 'takeaway':
            cur.execute("UPDATE sessions SET order_type = 'Takeaway', step = 'SHOW_MENU' WHERE phone_number = %s", (sender_phone,))
            show_menu(sender_phone, cur)
        
        elif interactive_id == 'dine_in':
            send_reply(sender_phone, "Please enter your Table Number:")
            cur.execute("UPDATE sessions SET order_type = 'Dine-in', step = 'ENTER_TABLE' WHERE phone_number = %s", (sender_phone,))
        else:
            send_reply(sender_phone, "Please tap one of the buttons above.")
            
    # --- STATE 2: ENTER TABLE (Only for Dine-in) ---
    elif step == 'ENTER_TABLE':
        if msg_type == 'text':
            cur.execute("UPDATE sessions SET table_number = %s, step = 'SHOW_MENU' WHERE phone_number = %s", (message['text']['body'], sender_phone))
            show_menu(sender_phone, cur)

    # --- STATE 3: MENU SELECTION ---
    elif step == 'SHOW_MENU' or step == 'CHOOSE_ITEM':
        if interactive_id:
            cur.execute("UPDATE sessions SET temp_item_id = %s, step = 'CHOOSE_QUANTITY' WHERE phone_number = %s", (int(interactive_id), sender_phone))
            send_reply(sender_phone, "How many plates would you like? (Please type a number)")

    # --- STATE 4: DYNAMIC QUANTITY & INVENTORY CHECK ---
    elif step == 'CHOOSE_QUANTITY':
        if msg_type == 'text':
            try:
                qty = int(incoming_text)
                if qty <= 0:
                    send_reply(sender_phone, "Please enter a valid quantity (1 or more).")
                    conn.close()
                    return
            except ValueError:
                send_reply(sender_phone, "That doesn't look like a valid number. Please type how many plates you would like.")
                conn.close()
                return

            item_id = session['temp_item_id']
            cur.execute("SELECT * FROM menu WHERE id = %s", (item_id,))
            item = cur.fetchone()
            
            # Inventory Validation
            if qty > item['inventory']:
                send_reply(sender_phone, f"Sorry, we only have {item['inventory']} plates of {item['name']} left right now. Please enter a smaller number.")
                conn.close()
                return
            
            cart = session['cart'] if session['cart'] else []
            cart.append({"id": item['id'], "name": item['name'], "price": item['price'], "qty": qty})
            
            cur.execute("UPDATE sessions SET cart = %s, step = 'CART_OPTIONS' WHERE phone_number = %s", (json.dumps(cart), sender_phone))
            
            # Generate summary
            total = sum(c['price'] * c['qty'] for c in cart)
            summary = "🛒 *Cart Preview*\n"
            for c in cart:
                summary += f"• {c['qty']}x {c['name']} (₹{c['price'] * c['qty']})\n"
            summary += f"\n*Total: ₹{total}*"
            
            send_button_message(sender_phone, summary, [
                {"id": "add_item", "title": "➕ Add Item"},
                {"id": "checkout", "title": "💳 Checkout"},
                {"id": "cancel", "title": "❌ Cancel"}
            ])

    # --- STATE 5: CHECKOUT & PAYMENT ---
    elif step == 'CART_OPTIONS':
        if interactive_id == 'add_item':
            cur.execute("UPDATE sessions SET step = 'SHOW_MENU' WHERE phone_number = %s", (sender_phone,))
            show_menu(sender_phone, cur)
            
        elif interactive_id == 'cancel':
            cur.execute("DELETE FROM sessions WHERE phone_number = %s", (sender_phone,))
            send_reply(sender_phone, "Order cancelled. Say 'Hi' whenever you are hungry again!")
            
        elif interactive_id == 'checkout':
            cart = session['cart']
            total = sum(c['price'] * c['qty'] for c in cart)
            order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
            
            # Save final order to DB (no delivery address)
            cur.execute("""
                INSERT INTO orders (order_id, phone_number, order_type, table_number, total_amount, cart_items, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
            """, (order_id, sender_phone, session['order_type'], session['table_number'], total, json.dumps(cart)))
            
            # Generate Payment Link
            payment_link_data = {
                "amount": total * 100, 
                "currency": "INR",
                "description": "Watave's Biriyani Point",
                "customer": {"contact": f"+{sender_phone}"},
                "notes": {"order_id": order_id, "phone_number": sender_phone}
            }
            link = rzp_client.payment_link.create(payment_link_data)['short_url']
            
            msg = f"🧾 *Final Checkout*\nTotal Amount: ₹{total}\n\nPlease click below to pay and confirm your order:\n{link}"
            send_reply(sender_phone, msg)
            cur.execute("UPDATE sessions SET step = 'AWAITING_PAYMENT' WHERE phone_number = %s", (sender_phone,))

    conn.commit()
    conn.close()

# --- META CLOUD API HELPERS ---
def show_menu(phone_number, cur):
    """Fetches menu from DB and sends as an interactive list."""
    cur.execute("SELECT * FROM menu WHERE inventory > 0")
    items = cur.fetchall()
    
    if not items:
        send_reply(phone_number, "Sorry, we are completely sold out right now! 😔")
        return
        
    # Hidden inventory count - only showing the price in the description now
    rows = [{"id": str(i['id']), "title": i['name'], "description": f"₹{i['price']}"} for i in items]
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": "Please select an item from our menu:"},
            "action": {
                "button": "View Menu",
                "sections": [{"title": "Available Items", "rows": rows}]
            }
        }
    }
    requests.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages", headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}, json=payload)

def send_button_message(phone_number, text, buttons):
    """Sends up to 3 interactive buttons."""
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [{"type": "reply", "reply": {"id": b['id'], "title": b['title']}} for b in buttons]
            }
        }
    }
    requests.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages", headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}, json=payload)

def send_reply(phone_number, text_message):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": text_message}
    }
    requests.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages", headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}, json=payload)

if __name__ == '__main__':
    app.run(port=5000, debug=True)