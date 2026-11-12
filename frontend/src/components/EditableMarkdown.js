import React, { useState, useRef, useEffect } from 'react';
import MarkdownRenderer from './MarkdownContent';

function EditableMarkdown({ value, onChange, placeholder, minRows = 4, label }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || '');
  const textareaRef = useRef(null);

  useEffect(() => {
    setDraft(value || '');
  }, [value]);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      const len = textareaRef.current.value.length;
      textareaRef.current.setSelectionRange(len, len);
    }
  }, [editing]);

  const commit = (text) => {
    if (text !== (value || '')) {
      onChange(text);
    }
  };

  const startEditing = () => {
    setDraft(value || '');
    setEditing(true);
  };

  const finishEditing = () => {
    setEditing(false);
    commit(draft);
  };

  const handlePaste = () => {
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        const pasted = textareaRef.current.value;
        setDraft(pasted);
        commit(pasted);
        setEditing(false);
      }
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setDraft(value || '');
      setEditing(false);
    }
  };

  return (
    <div className="editable-markdown">
      {label && <label className="editable-markdown-label">{label}</label>}
      {editing ? (
        <textarea
          ref={textareaRef}
          className="form-control editable-markdown-textarea"
          rows={minRows}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={finishEditing}
          onPaste={handlePaste}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
        />
      ) : (
        <div
          className="editable-markdown-preview"
          onClick={startEditing}
          title="Clique para editar"
        >
          {value ? (
            <MarkdownRenderer content={value} />
          ) : (
            <span className="editable-markdown-placeholder">
              {placeholder || 'Clique para adicionar conteudo...'}
            </span>
          )}
          <span className="editable-markdown-edit-hint">Editar</span>
        </div>
      )}
    </div>
  );
}

export default EditableMarkdown;