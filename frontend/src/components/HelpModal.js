import React from 'react';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

const SECOES = [
  {
    titulo: 'Material do tópico',
    itens: [
      {
        nome: 'Adicionar arquivos',
        texto: 'Envie PDFs, apresentações (PPT/PPTX), documentos Word (DOC/DOCX) e imagens (PNG, JPG ou JPEG) de questões. Elas entram na aba Responder e podem ser anotadas no quadro branco.',
      },
      {
        nome: 'Adicionar material de apoio',
        texto: 'Envie textos e PDFs de teoria. Esse material alimenta a busca do app: questões, flashcards e estratégias usam os trechos certos do seu material.',
      },
    ],
  },
  {
    titulo: 'Ferramentas de estudo',
    itens: [
      {
        nome: 'Gerar questões',
        texto: 'Cria uma lista de exercícios sobre o tema, com os tipos e a quantidade que você escolher. Depois, você insere no tópico, salva no histórico ou descarta.',
      },
      {
        nome: 'Flashcards',
        texto: 'Monta cartões de revisão a partir do material do tópico ou do tema digitado, ideais para revisão espaçada.',
      },
      {
        nome: 'Estratégia de estudo',
        texto: 'Informe sua dedicação diária e a data da prova: o app monta um plano com cronograma, revisões e a tabela de técnicas estudadas.',
      },
      {
        nome: 'Pesquisar artigos',
        texto: 'Busca referências acadêmicas sobre o assunto e adiciona os PDFs encontrados ao tópico.',
      },
    ],
  },
  {
    titulo: 'Responder e praticar',
    itens: [
      {
        nome: 'Verificação de resposta',
        texto: 'Na aba Responder, cada questão tem editor de resposta: escreva ou cole a sua e peça a verificação. O feedback compara com o material do tópico e pode gerar uma explicação com os trechos usados como base.',
      },
      {
        nome: 'Quadro branco',
        texto: 'Desenhe, escreva e cole imagens ao lado da questão atual. O quadro salva sozinho, pode ir para tela cheia e ser exportado.',
      },
      {
        nome: 'Anotações',
        texto: 'Na aba Anotações, escreva suas observações sobre a questão atual. O texto salva sozinho.',
      },
      {
        nome: 'Adicionar questão',
        texto: 'Use o botão de nova questão para criar uma questão manual com enunciado, tipo, resposta e explicação.',
      },
    ],
  },
  {
    titulo: 'Navegação das páginas',
    itens: [
      {
        nome: 'Filtro',
        texto: 'No topo do carrossel, filtre por arquivo enviado ou só por questões geradas. As setas e o contador seguem o filtro.',
      },
      {
        nome: 'Anterior e Próximo',
        texto: 'Navegue entre as páginas do tópico. Com o filtro ativo, as setas percorrem apenas o grupo escolhido.',
      },
    ],
  },
  {
    titulo: 'Sessões, tarefas e histórico',
    itens: [
      {
        nome: 'Sessões e histórico',
        texto: 'Sessões registram seu tempo de estudo por tópico e o histórico guarda as versões de estratégias, questões e explicações.',
      },
      {
        nome: 'Tarefas',
        texto: 'Gerações longas viram tarefas e continuam em segundo plano. O indicador de tarefas mostra o andamento de cada uma.',
      },
    ],
  },
];

function HelpModal({ isOpen, onClose }) {
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);

  if (!isOpen) return null;

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content ajuda-modal-conteudo">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>Como usar o Exercita AI</h2>
          <span className="close" onClick={onClose} aria-label="Fechar">&times;</span>
        </div>
        <p className="ajuda-intro">
          Cada tópico reúne o seu material e as ferramentas de estudo. O
          caminho mais comum é: envie o material, use as ferramentas de estudo
          para praticar e acompanhe seu progresso nas sessões.
        </p>
        {SECOES.map((secao) => (
          <div key={secao.titulo} className="ajuda-secao">
            <h3>{secao.titulo}</h3>
            {secao.itens.map((item) => (
              <div key={item.nome} className="ajuda-item">
                <strong>{item.nome}</strong>
                <span>{item.texto}</span>
              </div>
            ))}
          </div>
        ))}
        <p className="ajuda-dica">
          Dica: nomes específicos no tópico (matéria + foco) melhoram tudo que
          é gerado. Se o nome estiver genérico, o app avisa na criação e pode
          sugerir um nome melhor.
        </p>
      </div>
    </div>
  );
}

export default HelpModal;
