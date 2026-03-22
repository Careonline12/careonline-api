from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, sys, traceback


app = Flask(__name__)
CORS(app)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0'})


@app.route('/generate', methods=['POST'])
def generate():
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

