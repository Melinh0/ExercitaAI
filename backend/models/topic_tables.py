from models.user_model import db
from datetime import datetime


class Topic(db.Model):
    __tablename__ = 'topic'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='CASCADE'),
        nullable=False,
    )
    nome = db.Column(db.String(255), nullable=False)
    extras = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'nome', name='uq_topic_user_nome'),
    )

    imagens = db.relationship(
        'TopicImage',
        backref='topico',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='TopicImage.posicao',
    )
    notas = db.relationship(
        'TopicNote',
        backref='topico',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='TopicNote.posicao',
    )
    sessoes = db.relationship(
        'TopicSession',
        backref='topico',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='TopicSession.posicao',
    )
    estrategia = db.relationship(
        'TopicStrategy',
        backref='topico',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )


class TopicImage(db.Model):
    __tablename__ = 'topic_image'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('topic.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    imagem = db.Column(db.Text)
    posicao = db.Column(db.Integer, nullable=False, default=0)
    data = db.Column(db.Text)
    is_text_question = db.Column(db.Boolean)
    texto = db.Column(db.Text)
    extras = db.Column(db.Text)

    questoes = db.relationship(
        'QuestionRow',
        backref='imagem_ref',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='QuestionRow.posicao',
    )


class QuestionRow(db.Model):
    __tablename__ = 'question'

    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(
        db.Integer,
        db.ForeignKey('topic_image.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    posicao = db.Column(db.Integer, nullable=False, default=0)
    questao = db.Column(db.Text)
    tipo = db.Column(db.Text)
    resposta = db.Column(db.Text)
    explicacao = db.Column(db.Text)
    whiteboard_img = db.Column(db.Text)
    enunciado = db.Column(db.Text)
    extras = db.Column(db.Text)


class TopicNote(db.Model):
    __tablename__ = 'note'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('topic.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    posicao = db.Column(db.Integer, nullable=False, default=0)
    note_id = db.Column(db.Text)
    image_filename = db.Column(db.Text)
    text = db.Column(db.Text)
    timestamp = db.Column(db.Text)
    extras = db.Column(db.Text)


class TopicSession(db.Model):
    __tablename__ = 'study_session'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('topic.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    posicao = db.Column(db.Integer, nullable=False, default=0)
    dados = db.Column(db.Text, nullable=False)


class TopicStrategy(db.Model):
    __tablename__ = 'study_strategy'

    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('topic.id', ondelete='CASCADE'),
        primary_key=True,
    )
    dados = db.Column(db.Text)


class TopicInstructionMemory(db.Model):
    __tablename__ = 'topic_instruction_memory'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('topic.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    instrucao = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.Text, default='geral')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_topic_instruction_memory_topic_tipo', 'topic_id', 'tipo'),
    )
