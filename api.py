from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, sys, traceback, json
import stripe

app = Flask(__name__)
CORS(app)

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.0'})

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Create a Stripe Checkout session for the 29€ guide."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Données manquantes'}), 400

        quiz_data = data.get('quiz_data', {})
        success_url = data.get('success_url', 'https://careonline.fr?payment=success')
        cancel_url = data.get('cancel_url', 'https://careonline.fr?payment=cancelled')

        # Store quiz data in Stripe metadata (max 500 chars per key)
        metadata = {
            'prenom': quiz_data.get('prenom', ''),
            'nom': quiz_data.get('nom', ''),
            'email': quiz_data.get('email', ''),
            'preoccupation': quiz_data.get('premiere_preoccupation', ''),
            'quiz_data_stored': 'true',
        }

        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': 'Guide Beauté Personnalisé — care.on.line',
                        'description': f'Guide personnalisé pour {quiz_data.get("prenom", "vous")} — Diagnostic peau + Routines matin/soir + Shopping list',
                    },
                    'unit_amount': 2900,  # 29.00 EUR in cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=quiz_data.get('email', None),
            metadata=metadata,
        )

        return jsonify({
            'checkout_url': session.url,
            'session_id': session.id,
        })

    except stripe.error.StripeError as e:
        traceback.print_exc()
        return jsonify({'error': f'Erreur Stripe: {str(e)}'}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events (payment completed → generate PDF → send email)."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload)

        if event.get('type') == 'checkout.session.completed':
            session = event['data']['object']
            customer_email = session.get('customer_email', '')
            metadata = session.get('metadata', {})

            print(f"✅ Paiement reçu de {customer_email}")
            print(f"   Prénom: {metadata.get('prenom')}")
            print(f"   Préoccupation: {metadata.get('preoccupation')}")

            # TODO: Retrieve full quiz data and generate PDF
            # TODO: Send PDF via email (Resend)

        return jsonify({'status': 'ok'})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


@app.route('/generate', methods=['POST'])
def generate():
    """Generate a personalized beauty guide PDF."""
    try:
        quiz_data = request.get_json()
        if not quiz_data:
            return jsonify({'error': 'Données manquantes'}), 400

        prenom = quiz_data.get('prenom', 'client')
        safe_name = ''.join(c for c in prenom if c.isalnum())
        output_path = f"/tmp/guide_{safe_name}_{os.urandom(4).hex()}.pdf"

        sys.path.insert(0, os.path.dirname(__file__))
        from engine import run
        run(quiz_data, os.path.join(os.path.dirname(__file__), 'Data_Produits.xlsx'), output_path)

        if not os.path.exists(output_path):
            return jsonify({'error': 'PDF non généré'}), 500

        return send_file(
            output_path,
            as_attachment=True,
            download_name=f'guide_beaute_{safe_name}.pdf',
            mimetype='application/pdf'
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
