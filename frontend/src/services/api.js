import axios from 'axios';

const api = axios.create({
  baseURL: '',
  headers: { 'Accept': 'application/json' },
});

export const EVENTO_SISTEMA_INDISPONIVEL = 'sistema-indisponivel';
export const EVENTO_SISTEMA_DISPONIVEL = 'sistema-disponivel';

const avisarIndisponivel = () => {
  try {
    window.dispatchEvent(new Event(EVENTO_SISTEMA_INDISPONIVEL));
  } catch (err) {
    console.error('Erro ao avisar indisponibilidade:', err);
  }
};

const avisarDisponivel = () => {
  try {
    window.dispatchEvent(new Event(EVENTO_SISTEMA_DISPONIVEL));
  } catch (err) {
    console.error('Erro ao avisar disponibilidade:', err);
  }
};

const ehIndisponibilidade = (erro) => {
  const status = erro.response && erro.response.status;
  return !erro.response || status === 502 || status === 503 || status === 504;
};

api.interceptors.response.use(
  (resposta) => {
    avisarDisponivel();
    return resposta;
  },
  (erro) => {
    if (ehIndisponibilidade(erro)) {
      avisarIndisponivel();
    }
    return Promise.reject(erro);
  }
);

export const verificarSaude = () => api.get(`/api/health?_t=${Date.now()}`);

export const getTopics = () => api.get(`/api/topics?_t=${Date.now()}`);
export const getTopic = (topicName) => api.get(`/api/topics/${topicName}`);
export const suggestTopicName = (nome, descricao) =>
  api.post('/api/topics/suggest-name', { nome, descricao });

export const createTopic = (name) => {
  const formData = new URLSearchParams();
  formData.append('nome', name);
  return api.post('/api/topics', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

export const renameTopic = (oldName, newName) => {
  const formData = new URLSearchParams();
  formData.append('new_name', newName);
  return api.post(`/topic/${oldName}/rename`, formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

export const deleteImage = (topicName, filename) =>
  api.post(`/topic/${topicName}/delete_image/${encodeURIComponent(filename)}`);

export const deleteTopic = (topicName) => api.post(`/topic/${topicName}/delete`);

export const addQuestion = (topicName, imageFilename, data) => {
  const formData = new URLSearchParams();
  formData.append('image_filename', imageFilename);
  formData.append('questao_num', data.questao_num);
  formData.append('tipo', data.tipo || '');
  formData.append('resposta', data.resposta || '');
  formData.append('explicacao', data.explicacao || '');
  formData.append('idx', data.idx || 0);
  return api.post(`/topic/${topicName}/add_question`, formData);
};

export const addTextQuestion = (topicName, questionData) => {
  return api.post(`/topic/${topicName}/add_text_question`, questionData, {
    headers: { 'Content-Type': 'application/json' },
  });
};

export const addTextQuestions = (topicName, questions) => {
  return api.post(`/topic/${topicName}/add_text_questions`, { questions }, {
    headers: { 'Content-Type': 'application/json' },
  });
};

export const updateQuestion = (topicName, imageFilename, qIdx, data) => {
  const formData = new URLSearchParams();
  formData.append('topic', topicName);
  formData.append('image_filename', imageFilename);
  formData.append('q_idx', qIdx);
  formData.append('resposta', data.resposta);
  formData.append('explicacao', data.explicacao);
  if (data.enunciado !== undefined) formData.append('enunciado', data.enunciado);
  formData.append('idx', data.idx);
  if (data.original_json) formData.append('original_json', data.original_json);
  return api.post('/save', formData);
};

export const deleteQuestion = (topicName, imageFilename, qIdx, idx) => {
  const formData = new URLSearchParams();
  formData.append('image_filename', imageFilename);
  formData.append('q_idx', qIdx);
  formData.append('idx', idx);
  return api.post(`/topic/${topicName}/delete_question`, formData);
};

export const getModels = (visionOnly = false) =>
  api.get(visionOnly ? '/api/models?vision=1' : '/api/models');
export const getModelInfo = (models) => {
  if (Array.isArray(models) && models.length > 0) {
    return api.get('/api/model_info', { params: { models: models.join(',') } });
  }
  return api.get('/api/model_info');
};

export const saveWhiteboard = (topicName, data) =>
  api.post('/save_whiteboard', data);

export const uploadPDF = (topicName, files) => {
  const formData = new FormData();
  const lista = Array.isArray(files) ? files : [files];
  lista.forEach((file) => formData.append('pdf', file));
  return api.post(`/topic/${topicName}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const uploadImages = (topicName, files) => {
  const formData = new FormData();
  files.forEach((file) => formData.append('images', file));
  return api.post(`/topic/${topicName}/upload_images`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const extractImages = (topicName, pdfPath) => {
  const formData = new URLSearchParams();
  formData.append('pdf_path', pdfPath);
  return api.post(`/topic/${topicName}/extrair`, formData);
};

export const listFiles = (topicName) => api.get(`/topic/${topicName}/files`);

export const listMaterialFiles = (topicName) => api.get(`/topic/${topicName}/material_files`);

export const deleteFile = (topicName, filename) =>
  api.post(`/topic/${topicName}/delete_file/${encodeURIComponent(filename)}`);

export const getDownloadImageUrl = (topicName, filename) =>
  `/topic/${topicName}/download_image/${encodeURIComponent(filename)}`;

export const getDownloadAllImagesUrl = (topicName) =>
  `/topic/${topicName}/download_all_images`;

export const getDownloadTextResolutionsUrl = (topicName) =>
  `/topic/${topicName}/download_text_resolutions`;

export const getDownloadWhiteboardsUrl = (topicName) =>
  `/topic/${topicName}/download_whiteboards`;

export const getDownloadQuestionTextUrl = (topicName, imageFilename, qIdx, idx) =>
  `/topic/${topicName}/download_question_text/${encodeURIComponent(imageFilename)}/${qIdx}?idx=${idx}`;

export const getDownloadQuestionWhiteboardUrl = (topicName, imageFilename, qIdx, idx) =>
  `/topic/${topicName}/download_question_whiteboard/${encodeURIComponent(imageFilename)}/${qIdx}?idx=${idx}`;

export const getDownloadWhiteboardLivreUrl = (topicName, imageFilename, idx) =>
  `/topic/${topicName}/download_whiteboard_livre/${encodeURIComponent(imageFilename)}?idx=${idx}`;

export const saveAnswers = (topic, sessionData) =>
  api.post('/save_answers', { topic, session_data: sessionData });

export const getSessions = (topicName) => api.get(`/topic/${topicName}/sessions`);
export const updateSession = (topicName, sessionIdx, sessionData) =>
  api.put(`/topic/${topicName}/sessions/${sessionIdx}`, sessionData);

export const deleteSession = (topicName, sessionIdx) =>
  api.delete(`/topic/${topicName}/sessions/${sessionIdx}`);

export const evaluateAnswer = (dados) => api.post('/evaluate_answer', dados);

export const uploadRAG = (topicName, files) => {
  const formData = new FormData();
  const fileArray = Array.isArray(files) ? files : [files];
  fileArray.forEach(f => formData.append('files', f));
  return api.post(`/topic/${topicName}/upload_rag`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const getTaskStatus = (taskId) => api.get(`/tasks/${taskId}`);

export const getNotes = (topicName, params) => api.get(`/topic/${topicName}/notes`, { params });
export const addNote = (topicName, data) => api.post(`/topic/${topicName}/notes`, data);
export const updateNote = (topicName, noteId, data) => api.put(`/topic/${topicName}/notes/${noteId}`, data);
export const deleteNote = (topicName, noteId) => api.delete(`/topic/${topicName}/notes/${noteId}`);

export const getStudyStrategy = (topicName) => api.get(`/topic/${topicName}/study_strategy`);
export const getStudyStrategyHistory = (topicName) =>
  api.get(`/topic/${topicName}/study_strategy`, { params: { historico: 1 } });
export const saveStudyStrategyHistory = (topicName, estrategia) =>
  api.post(`/topic/${topicName}/study_strategy`, { action: 'salvar_historico', estrategia });
export const restoreStudyStrategy = (topicName, indice) =>
  api.post(`/topic/${topicName}/study_strategy`, { action: 'restaurar_estrategia', indice });
export const deleteStudyStrategyHistory = (topicName, indice) =>
  api.post(`/topic/${topicName}/study_strategy`, { action: 'remover_historico', indice });

export const getTopicImageUrl = (topicName, filename) =>
  `/topic/${topicName}/image/${encodeURIComponent(filename)}`;

export const startAsyncTask = (type, params) =>
  api.post('/tasks/start', { type, params });

export const listTasks = () => api.get('/tasks');
export const getTask = (taskId) => api.get(`/tasks/${taskId}`);
export const deleteTask = (taskId) => api.delete(`/tasks/${taskId}`);

export const searchArticles = (query) => api.post('/search_articles', { query });

export const analyzeWithImageAsync = (topic, imageFilename, model, extraPrompt = '', transcriptionMethod = 'tesseract') =>
  startAsyncTask('analyze_with_image', {
    topic,
    image_filename: imageFilename,
    model,
    extra_prompt: extraPrompt,
    transcription_method: transcriptionMethod,
    ocr_model: transcriptionMethod === 'llm' ? model : undefined,
  });

export const analyzeFullDocumentAsync = (topic, model, extraPrompt = '', transcriptionMethod = 'tesseract') =>
  startAsyncTask('analyze_full_document', {
    topic,
    model,
    extra_prompt: extraPrompt,
    transcription_method: transcriptionMethod,
    ocr_model: transcriptionMethod === 'llm' ? model : undefined,
  });

export const analyzeImageInsightAsync = (topic, imageFilename, model, extraPrompt = '', transcriptionMethod = 'tesseract') =>
  startAsyncTask('analyze_image_insight', {
    topic,
    image_filename: imageFilename,
    model,
    extra_prompt: extraPrompt,
    transcription_method: transcriptionMethod,
    ocr_model: transcriptionMethod === 'llm' ? model : undefined,
  });

export const enhanceQuestionAsync = (topic, imageFilename, qIdx, enunciado, explicacao, resposta, customPrompt, model) =>
  startAsyncTask('enhance_question', {
    topic,
    image_filename: imageFilename,
    q_idx: qIdx,
    enunciado,
    explicacao,
    resposta,
    custom_prompt: customPrompt,
    model,
  });

export const generateQuestionsAsync = (topic, questionTypes, numQuestions, customInstructions, model) =>
  startAsyncTask('generate_questions', {
    topic,
    question_types: questionTypes,
    num_questions: numQuestions,
    custom_instructions: customInstructions,
    model,
  });

export const generateFlashcardsAsync = (topic, subject, customInstructions, model, maxFlashcards) =>
  startAsyncTask('generate_flashcards', {
    topic,
    subject,
    custom_instructions: customInstructions,
    model,
    max_flashcards: maxFlashcards || 12,
  });

export const studyStrategyAsync = (topic, dedication) =>
  startAsyncTask('study_strategy', { topic, dedication });

export const searchArticlesAsync = (query) =>
  startAsyncTask('search_articles', { query });

export const suggestPromptsAsync = (topic, imageFilename, qIdx, enunciado, resposta, explicacao, model) =>
  startAsyncTask('suggest_prompts', {
    topic,
    image_filename: imageFilename,
    q_idx: qIdx,
    enunciado,
    resposta,
    explicacao,
    model,
  });