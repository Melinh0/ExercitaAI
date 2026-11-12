from flask import Blueprint, request, jsonify
from models.topic_model import TopicModel
from flask_login import login_required, current_user
import uuid
from datetime import datetime

note_bp = Blueprint('note', __name__, url_prefix='/topic/<topic_name>/notes')

@note_bp.route('', methods=['GET'])
@login_required
def list_notes(topic_name):
    image_filename = request.args.get('image_filename')
    notes = TopicModel.get_notes(current_user, topic_name)
    if image_filename is not None:
        notes = [n for n in notes if n.get('image_filename') == image_filename]
    return jsonify(notes)

@note_bp.route('', methods=['POST'])
@login_required
def add_note(topic_name):
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Texto é obrigatório'}), 400
    note = {
        'id': str(uuid.uuid4()),
        'image_filename': data.get('image_filename'),
        'text': data['text'],
        'timestamp': datetime.now().isoformat()
    }
    TopicModel.add_note(current_user, topic_name, note)
    return jsonify(note), 201

@note_bp.route('/<note_id>', methods=['PUT'])
@login_required
def update_note(topic_name, note_id):
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Texto é obrigatório'}), 400
    if TopicModel.update_note(current_user, topic_name, note_id, data['text']):
        return jsonify({'success': True})
    return jsonify({'error': 'Nota não encontrada'}), 404

@note_bp.route('/<note_id>', methods=['DELETE'])
@login_required
def delete_note(topic_name, note_id):
    TopicModel.delete_note(current_user, topic_name, note_id)
    return jsonify({'success': True})