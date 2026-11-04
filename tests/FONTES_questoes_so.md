# Fontes do banco de questões de Sistemas Operacionais

> Documento de apoio do TCC/artigo. Referência para citar as questões usadas
> na avaliação do RAG (`tests/questoes_so.json`, consumido por `readme.py`).
> Gerado a partir do banco consolidado — não edite manualmente.

## Metodologia de seleção

1. **Pesquisa dirigida na web** por questões de Sistemas Operacionais em
   fontes públicas, separadas em quatro lotes temáticos: processos/threads e
   escalonamento; sincronização e deadlocks; memória e paginasção; sistemas de
   arquivos, E/S, virtualização e redes.
2. **Verificação de cada fonte:** todo URL incluído foi acessado e o conteúdo
   da questão confirmado antes do registro — por leitura direta da página ou
   do PDF; nas fontes com proteção anti-bot (qconcurses.com), o enunciado foi
   confirmado textualmente por snippet do índice de busca (Google) apontando
   para a mesma URL. Fontes que não passaram na verificação foram descartadas
   — nenhuma URL foi inventada. Como checagem final, as 36 URLs do banco foram
   submetidas a requisição HTTP: 28 responderam 200 diretamente e as 8
   restantes (todas com bloqueio de robô) foram confirmadas pelo índice de
   busca, como descrito acima.
3. **Preservação do original:** enunciado e alternativas mantidos como
   publicados (apenas normalização de formatação).
4. **Gabarito:** quando a fonte publica o gabarito oficial, ele é usado
   diretamente (campo `gabarito_publicado_pela_fonte: true`); quando não
   publica, o gabarito foi determinado tecnicamente com justificativa própria
   (campo `false`), podendo ser conferido contra o livro de referência.
5. **Diversificação:** mínimo de oito fontes distintas por lote e no máximo
   três questões por mesma URL, para evitar dependência de um único autor ou
   banca.
6. **Aderência ao RAG:** os temas foram escolhidos por serem cobertos pelo
   livro indexado (*Sistemas Operacionais Modernos*, Tanenbaum/Bos), de modo
   que o contexto recuperado pelo RAG tenha chance real de alterar a resposta —
   é justamente o diferencial que se deseja medir.
7. **Formato textual:** priorizaram-se questões que não dependem de diagramas,
   pois o teste transcreve o enunciado para imagem de texto e o modelo responde
   por OCR.

## Motivo da escolha das fontes

| Critério | Por que foi adotado |
|----------|---------------------|
| Aderência ao livro de referência | As questões precisam ser respondíveis com o conteúdo do PDF indexado; sem isso, o RAG não teria como demonstrar impacto. |
| Verificabilidade | Cada fonte tem URL completa e data de acesso, permitindo reprodutibilidade da coleta (requisito de rigor acadêmico). |
| Autoridade | Provas oficiais de universidades públicas, institutos federais e concursos passam por revisão e publicam gabarito, reduzindo o risco de questão ambígua. |
| Diversificação de origem | Limitar questões por fonte evita o viés de estilo de uma única banca/autor e distribui o conjunto entre várias instituições. |
| Gabarito justificado | Toda questão tem justificativa técnica, o que permite ao juiz do teste avaliar a resposta contra um padrão objetivo em vez de interpretar o material isoladamente. |
| Sem dependência visual | O pipeline de teste usa OCR sobre imagem; questões com tabelas/diagramas introduziriam ruído alheio ao que se quer medir. |

## Questões

| ID | Tema | Gabarito publicado? | Fonte | URL | Acesso |
|----|------|---------------------|-------|-----|--------|
| `so_a01` | Escalonamento de CPU - Round-Robin (quantum) e taxa de resposta | Não* | Q5966 - Escalonamento por alternância circular (round-robin): problema com quantum muito longo — CESGRANRIO - BNDES (Prova Profissional Básico - Análise de Sistemas/Suporte, 2008), via banco de questões QConcursos | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/questoes/bac25d96-9a) | 2026-09-26 |
| `so_a02` | Escalonamento de CPU - SJF x FCFS (tempo de espera médio) | Não* | Q18902 - Tempo de espera médio com SJF versus FCFS (itens 51 a 60, sistema operacional) — CESPE/CEBRASPE - ANAC (Prova Analista Administrativo - Tecnologia da Informação, 2009), via banco de questões QConcursos | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/questoes/bd9f4234-e0) | 2026-09-26 |
| `so_a03` | Processos - processos órfãos, zumbis e prioridade no Linux | Sim | Q914426 - Gerenciamento de processos no sistema operacional Linux (gabarito comentado publicado na página) — FGV - MPE-AL (Prova Analista do Ministério Público, 2018), via banco de questões QConcursos | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/questoes/21fade16-86) | 2026-09-26 |
| `so_a04` | Multiprocessamento - multiprocessador com memória compartilhada | Não* | Q1057727 - Sistema operacional multiprocessador com memória compartilhada — CESPE/CEBRASPE - MPC-PA (Prova Analista Ministerial - Tecnologia da Informação, 2019), via banco de questões QConcursos | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/questoes/fad72b0b-0c) | 2026-09-26 |
| `so_a05` | Escalonamento de CPU - preempção | Não* | Questões de Algoritmo de Escalonamento (Sistemas Operacionais) - item sobre escalonamento preemptivo — UDESC - CESPE/CEBRASPE (Técnico Universitário de Desenvolvimento, Analista de Suporte, 2026), via banco de questões Questões Estratégicas | [www.questoesestrategicas.com.br](https://www.questoesestrategicas.com.br/questoes/busca/assunto/algoritmo-de-escalonamento) | 2026-09-26 |
| `so_a06` | Processos e threads - relação entre processo e thread (Windows) | Não* | Questões de Threads (Sistemas Operacionais) - relação entre processos e threads no Windows — Prefeitura Municipal de Guarujá do Sul - AMEOSC (Professor(a) de Informática, 2025), via banco de questões Questões Estratégicas | [www.questoesestrategicas.com.br](https://www.questoesestrategicas.com.br/questoes/busca/assunto/threads) | 2026-09-26 |
| `so_a07` | Processos e threads - o que é privativo de cada thread | Não* | Questões de Threads (Sistemas Operacionais) - itens específicos de cada thread — Companhia Nacional de Abastecimento (CONAB) - CONSULPAM (Analista em Tecnologia da Infraestrutura, 2025), via banco de questões Questões Estratégicas | [www.questoesestrategicas.com.br](https://www.questoesestrategicas.com.br/questoes/busca/assunto/threads) | 2026-09-26 |
| `so_a08` | Processos e threads - múltiplas threads em servidor web | Não* | Questões de Threads (Sistemas Operacionais) - servidor web baseado em threads — Câmara de Caraguatatuba - VUNESP (Agente de Informática, 2026), via banco de questões Questões Estratégicas | [www.questoesestrategicas.com.br](https://www.questoesestrategicas.com.br/questoes/busca/assunto/threads) | 2026-09-26 |
| `so_a09` | Escalonamento de CPU - sistema de tempo compartilhado | Sim | TE355 - Sistemas Operacionais Embarcados - Primeira Prova (18/10/2024), questão 1 (itens V/F) com gabarito publicado — Universidade Federal do Paraná (UFPR) - Engenharia Elétrica, Prof. Carlos Marcelo Pedroso | [www.eletrica.ufpr.br](http://www.eletrica.ufpr.br/pedroso/2024/TE355/TE355Prova1.pdf.pdf) | 2026-09-26 |
| `so_a10` | Processos - criação de processos e invocação de programas | Não* | Questões de Provas de Períodos Anteriores - Sistemas Operacionais (2010/1), questão 5 — Universidade Federal do Espírito Santo (UFES) - Material do professor Wilson Zandoná Eguia | [www.inf.ufes.br](https://www.inf.ufes.br/~zegonc/material/Sistemas_Operacionais/Questoes%20de%20Provas%20Anteriores.pdf) | 2026-09-26 |
| `so_a11` | Escalonamento de CPU - prioridade x preempção | Não* | Lista de Exercícios 1 - Sistemas Operacionais I - INF01142 (coletânea de questões de prova), exercício 1 - a fonte declara não haver gabarito — Universidade Federal do Rio Grande do Sul (UFRGS) - Instituto de Informática | [www.inf.ufrgs.br](https://www.inf.ufrgs.br/~asc/sisop/pdf/lista_cpu.pdf) | 2026-09-26 |
| `so_a12` | Processos - estados do processo e transições | Não* | Lista de Exercícios 1 - Sistemas Operacionais I - INF01142 (coletânea de questões de prova), exercício 4 - a fonte declara não haver gabarito — Universidade Federal do Rio Grande do Sul (UFRGS) - Instituto de Informática | [www.inf.ufrgs.br](https://www.inf.ufrgs.br/~asc/sisop/pdf/lista_cpu.pdf) | 2026-09-26 |
| `so_a13` | Processos - bloco de controle de processo (PCB) | Não* | Exercícios de Revisão 1 - MC504 Sistemas Operacionais (Versão 2025a), questão 5 - Processos e Threads — Universidade Estadual de Campinas (UNICAMP) - Instituto de Computação, Prof. Isaías Bittencourt Felzmann | [ic.unicamp.br](https://ic.unicamp.br/~isaias/materiais/mc504/Lista1.1.pdf) | 2026-09-26 |
| `so_b01` | Deadlock - algoritmo do Banqueiro (evitação de deadlocks) | Sim | Sistemas Operacionais – Deadlock (questão 1 - UFMA 2023, com gabarito publicado) — UFMA - Universidade Federal do Maranhão (Prova Analista de Tecnologia da Informação, 2023), via artigo do blog Gran Cursos Online | [blog.grancursosonline.com.br](https://blog.grancursosonline.com.br/sistemas-operacionais-deadlock) | 2026-09-26 |
| `so_b02` | Deadlock - quatro condições necessárias (Coffman) | Não* | Questões de Deadlock (Sistemas Operacionais) - questão BANESA/Técnico Bancário III Suporte — Banco do Estado de Sergipe S.A. (BANESA) - CESGRANRIO (Técnico Bancário III Suporte, 2025), via banco de questões Questões Estratégicas | [www.questoesestrategicas.com.br](https://www.questoesestrategicas.com.br/questoes/busca/assunto/deadlock) | 2026-09-26 |
| `so_b03` | Deadlock - grafo de alocação de recursos com múltiplas instâncias | Não* | Questões de Deadlock (Sistemas Operacionais) - questão IF SUL - MG 2026 (grafo de alocação de recursos) — Instituto Federal de Educação, Ciência e Tecnologia do Sul de Minas Gerais (IF SUL - MG) - Professor - Informática (2026), via banco de questões Questões Estratégicas | [www.questoesestrategicas.com.br](https://www.questoesestrategicas.com.br/questoes/busca/assunto/deadlock) | 2026-09-26 |
| `so_b04` | Sincronização - semáforos bloqueantes e atomicidade em multiprocessadores (SMP) | Não* | Questões de Sistemas Operacionais - questão IF SUL - MG 2026 (semáforo bloqueante em SMP) — Instituto Federal de Educação, Ciência e Tecnologia do Sul de Minas Gerais (IF SUL - MG) - Professor - Informática (2026), via banco de questões Questões Estratégicas | [www.questoesestrategicas.com.br](https://www.questoesestrategicas.com.br/questoes/busca/assunto/sistemas-operacionais) | 2026-09-26 |
| `so_b05` | Deadlock - prevenção por ordenação de recursos (eliminação da espera circular) | Não* | Q4090992 - Prevenção de deadlock por ordem linear de solicitação de recursos — Instituto AOCP - IF-CE (Professor EBTT - Sistemas de Computação, 2026), via banco de questões QConcursos | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/disciplinas/tecnologia-da-informacao-sistemas-operacionais/deadlock/questoes) | 2026-09-26 |
| `so_b06` | Inanição (starvation) versus deadlock e escalonamento | Não* | Q4163946 - Starvation e deadlock em ambiente Linux de alta concorrência — IBADE - COREN-AM (Prova Analista de Sistemas, 2026), via banco de questões QConcursos | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/disciplinas/tecnologia-da-informacao-sistemas-operacionais/deadlock/questoes) | 2026-09-26 |
| `so_b07` | Sincronização - uso inadequado de semáforos e deadlock | Não* | Q4013961 - Semáforos para controle de regiões críticas (assertivas) — IF-PI - Instituto Federal do Piauí (Prova Professor EBTT - Informática, 2026), via banco de questões QConcursos | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/questoes/63662436-3f) | 2026-09-26 |
| `so_b08` | Seção crítica - requisitos (exclusão mútua, progresso, espera limitada) | Não* | Q1165413 - Requisitos da solução para o problema de seção crítica (questão 41 da prova) — Poder Judiciário/AC - IVIN (Prova, 2024), via simulados de Sistemas Operacionais do PCI Concursos | [www.pciconcursos.com.br](https://www.pciconcursos.com.br/simulados/informatica/sistemas-operacionais/15) | 2026-09-26 |
| `so_b09` | Deadlock - as quatro condições de Coffman avaliadas em assertivas | Não* | Q1070130 - Condições para a ocorrência de impasse (deadlock) — CONSULPAM - Prefeitura de Irauçuba/CE (Prova Técnico em Manutenção de Informática e Rede, 2022), via banco de questões Estude Grátis | [www.estudegratis.com.br](https://www.estudegratis.com.br/questao-de-concurso/1070130) | 2026-09-26 |
| `so_b10` | Sincronização - operação Down em semáforo com valor zero | Não* | Exercício de semáforos na sincronização de processos (CESGRANRIO 2025 - operação Down/FIFO) — CESGRANRIO (Prova, 2025), via banco de questões Didata | [didata.ai](https://didata.ai/banco-de-questoes/questoes/tecnologia-da-informacao/sistemas-operacionais/exercicio-de-semaforos-na-sincronizacao-de-processos/p974aenpsdkgbwmgb7rya78nb984thpq) | 2026-09-26 |
| `so_b11` | Deadlock - prevenção, evitação e estado inseguro (algoritmo do banqueiro) | Não* | Q1096276 - Deadlocks: condições, prevenção e estado inseguro (assertivas) — FUNDATEC - IFC SC (Prova Informática Hardware e Redes, 2026), via banco de questões Gabarite | [gabarite.com.br](https://gabarite.com.br/questoes-de-concursos/1096276-questao) | 2026-09-26 |
| `so_b12` | Sincronização - problema produtor-consumidor com semáforos e trincos | Sim | Exercícios de Sistemas Operativos - Capítulo 6 (Programação Concorrente), Exercício 2 - canal produtor-consumidor, com resolução publicada — Instituto Superior Técnico (IST), Universidade de Lisboa - disciplina de Sistemas Operativos (LEIC) | [groups.ist.utl.pt](https://groups.ist.utl.pt/~leic-so.daemon/2017-2018/teoricas_resolucoes) | 2026-09-26 |
| `so_b13` | Sincronização - variáveis de condição e trinco (garagem com N lugares) | Sim | Exercícios de Sistemas Operativos - Capítulo 6 (Programação Concorrente), Exercício 1 - garagem com N lugares, com resolução publicada — Instituto Superior Técnico (IST), Universidade de Lisboa - disciplina de Sistemas Operativos (LEIC) | [groups.ist.utl.pt](https://groups.ist.utl.pt/~leic-so.daemon/2017-2018/teoricas_resolucoes) | 2026-09-26 |
| `so_c01` | Gerência de memória - endereçamento lógico e físico (cálculo de bits) | Não* | 3ª Lista de Exercícios - Sistemas Operacionais (INF09344 / INF02780 / INF02828), Profa. Roberta Lima Gomes, questão 3 — Universidade Federal do Espírito Santo (UFES) - Instituto de Computação | [www.inf.ufes.br](https://www.inf.ufes.br/~zegonc/material/Sistemas_Operacionais/so-lista3.pdf) | 2026-09-26 |
| `so_c02` | Gerência de memória - veracidade de afirmativas sobre paginação, segmentação e MMU | Não* | 3ª Lista de Exercícios - Sistemas Operacionais (INF09344 / INF02780 / INF02828), Profa. Roberta Lima Gomes, questão 12 — Universidade Federal do Espírito Santo (UFES) - Instituto de Computação | [www.inf.ufes.br](https://www.inf.ufes.br/~zegonc/material/Sistemas_Operacionais/so-lista3.pdf) | 2026-09-26 |
| `so_c03` | Substituição de páginas - NRU, FIFO, LRU e segunda chance | Não* | Gerenciamento de Memória - Exercícios extraídos de Modern Operating Systems (A. Tanenbaum), LaSiD/UFBA, Prof. Raimundo Macêdo, exercício 5 — Universidade Federal da Bahia (UFBA) - Laboratório de Sistemas Distribuídos (LaSiD) / DCC | [www.macedo.ufba.br](http://www.macedo.ufba.br/gerenciamemoria2013.pdf) | 2026-09-26 |
| `so_c04` | Substituição de páginas - contagem de faltas em FIFO e LRU | Não* | Gerenciamento de Memória - Exercícios extraídos de Modern Operating Systems (A. Tanenbaum), LaSiD/UFBA, Prof. Raimundo Macêdo, exercício 6 — Universidade Federal da Bahia (UFBA) - Laboratório de Sistemas Distribuídos (LaSiD) / DCC | [www.macedo.ufba.br](http://www.macedo.ufba.br/gerenciamemoria2013.pdf) | 2026-09-26 |
| `so_c05` | Memória virtual - thrashing: definição, detecção e providências | Não* | Lista de Exercícios 2 - Sistemas Operacionais I N (INF01142) - coletânea de questões de prova de INF01142, questão 7 — Universidade Federal do Rio Grande do Sul (UFRGS) - Instituto de Informática | [www.inf.ufrgs.br](https://www.inf.ufrgs.br/~asc/sisop/pdf/lista_mem.pdf) | 2026-09-26 |
| `so_c06` | Gerência de memória particionada - first fit, best fit e worst fit | Não* | Lista de Exercícios 2 - Sistemas Operacionais I N (INF01142) - coletânea de questões de prova de INF01142, questão 10 — Universidade Federal do Rio Grande do Sul (UFRGS) - Instituto de Informática | [www.inf.ufrgs.br](https://www.inf.ufrgs.br/~asc/sisop/pdf/lista_mem.pdf) | 2026-09-26 |
| `so_c07` | Memória virtual - working set (conjunto de trabalho) | Não* | Lista de Exercícios 2 - Sistemas Operacionais I N (INF01142) - coletânea de questões de prova de INF01142, questão 38, item B — Universidade Federal do Rio Grande do Sul (UFRGS) - Instituto de Informática | [www.inf.ufrgs.br](https://www.inf.ufrgs.br/~asc/sisop/pdf/lista_mem.pdf) | 2026-09-26 |
| `so_c08` | Gerência de memória - paginação, memória virtual e algoritmos de substituição (veracidade) | Não* | Q4013960 - Prova IF-PI 2026, Professor EBTT - Informática, Sistemas Operacionais / Gerência de Memória (QConcursos) — Instituto Federal de Educação, Ciência e Tecnologia do Piauí (IF-PI) - banca própria (banco de questões: QConcursos) | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/questoes/6362f7cd-3f) | 2026-09-26 |
| `so_c09` | Gerência de memória - paginação, swap, falta de página e substituição de páginas | Não* | Q995561 - Prova CCV-UFC 2019, UFC - Técnico de Laboratório / Informática, Sistemas Operacionais / Gerência de Memória (QConcursos) — Universidade Federal do Ceará (UFC) - banca CCV-UFC (banco de questões: QConcursos) | [www.qconcursos.com](https://www.qconcursos.com/questoes-de-concursos/questoes/d0a40609-82) | 2026-09-26 |
| `so_c10` | Memória virtual - thrashing e TLB (tradução de endereços virtuais) | Não* | Questão 42 - Prova Assembleia Legislativa do Estado de Rondônia (AL-RO), Analista Legislativo de TI, FGV (2026) (Questões Estratégicas) — Assembleia Legislativa do Estado de Rondônia (AL-RO) - banca FGV (banco de questões: Questões Estratégicas) | [www.questoesestrategicas.com.br](https://www.questoesestrategicas.com.br/questoes/ver/8ac067a4c0c1c417) | 2026-09-26 |
| `so_c11` | Memória virtual - endereçamento de 32 bits e PAE | Sim | Prova PCDF: Comentários às Questões de TI para Perito Criminal (PCDF 2016), questão 54 — Polícia Civil do Distrito Federal (PCDF) - concurso Perito Criminal 2016 (banca IADES), comentado no blog Estratégia Concursos | [www.estrategiaconcursos.com.br](https://www.estrategiaconcursos.com.br/blog/prova-pcdf-2016-ti/) | 2026-09-26 |
| `so_c12` | Memória virtual - uso do armazenamento secundário como extensão da RAM | Sim | Sistemas Operacionais - Gerência de Memória: questão 1 - CESPE/CEBRASPE 2024, CTI (Tecnologista Pleno 2 - I, Indústria 4.0 e Governo Digital) — Centro de Tecnologia da Informação Renato Archer (CTI) - banca CESPE/CEBRASPE (2024), publicada no blog Gran Cursos Online | [blog.grancursosonline.com.br](https://blog.grancursosonline.com.br/sistemas-operacionais-gerencia-de-memoria/) | 2026-09-26 |
| `so_d01` | E/S e dispositivos - interrupções e polling | Não* | Caderno de Provas - Concurso Público Federal, Edital 06/2015 - Área: Informática/Organização e Arquitetura de Computadores e Sistemas Operacionais (questão 24) — Instituto Federal do Rio Grande do Sul (IFRS) | [ifrs.edu.br](https://ifrs.edu.br/wp-content/uploads/2017/08/Inform%C3%A1tica-Organiza%C3%A7%C3%A3o-e-Arquitetura-de-Computadores-20.pdf) | 2026-09-26 |
| `so_d02` | Redes e interconexão - comutação de circuitos | Não* | Caderno de Provas - Concurso Público Federal, Edital 06/2015 - Área: Informática/Organização e Arquitetura de Computadores e Sistemas Operacionais (questão 3) — Instituto Federal do Rio Grande do Sul (IFRS) | [ifrs.edu.br](https://ifrs.edu.br/wp-content/uploads/2017/08/Inform%C3%A1tica-Organiza%C3%A7%C3%A3o-e-Arquitetura-de-Computadores-20.pdf) | 2026-09-26 |
| `so_d03` | Redes e interconexão - topologias de rede (física e lógica) | Não* | Prova - Concurso SDS/PE, aplicação 2016 (CESPE/CEBRASPE), Caderno de Conhecimentos Específicos, questão 63 — CESPE/CEBRASPE - concurso SDS/PE (aplicação 2016) | [cdn.cebraspe.org.br](https://cdn.cebraspe.org.br/concursos/sds_pe_16_cientifica/arquivos/260SDSPE_008_01.PDF) | 2026-09-26 |
| `so_d04` | Virtualização - contêineres | Não* | Prova de Conhecimentos - Parte I (Prova Objetiva), Concurso SEBRAE, Edital 2024, questão 42 — SEBRAE (banca organizadora: CEBRASPE) | [cdn.cebraspe.org.br](https://cdn.cebraspe.org.br/concursos/sebrae_24/arquivos/004_SEBRAE_009_01.PDF) | 2026-09-26 |
| `so_d05` | Virtualização - hipervisores tipo 1 e tipo 2, paravirtualização | Não* | Prova Objetiva e Prova Discursiva - Analista Judiciário - Tecnologia da Informação / Analista de Segurança da Informação, Tipo 1 - Branca (questão 31) — Tribunal de Justiça do Estado do Rio de Janeiro (banca organizadora: FGV) | [conhecimento.fgv.br](https://conhecimento.fgv.br/sites/default/files/concursos/analista-judiciario-tecnologia-da-informacao-analista-de-seguranca-da-informacao-ns-a13-anaseguranca-tipo-1.pdf) | 2026-09-26 |
| `so_d06` | Sistemas de arquivos - tamanho máximo de arquivo (FAT32) | Não* | Caderno de Provas - Concurso Perito Criminal Federal, DGP/PF, aplicação 2018 (CESPE/CEBRASPE) - item 61 — CESPE/CEBRASPE - concurso Perito Criminal Federal (DGP/PF), 2018 | [apcf.org.br](https://apcf.org.br/wp-content/uploads/2022/02/perito_criminal_federal_area_3_informatica.pdf) | 2026-09-26 |
| `so_d07` | E/S e dispositivos - RAID (striping) | Não* | Caderno de Provas - Concurso Perito Criminal Federal, DGP/PF, aplicação 2018 (CESPE/CEBRASPE) - item 109 — CESPE/CEBRASPE - concurso Perito Criminal Federal (DGP/PF), 2018 | [apcf.org.br](https://apcf.org.br/wp-content/uploads/2022/02/perito_criminal_federal_area_3_informatica.pdf) | 2026-09-26 |
| `so_d08` | Redes e interconexão - camada de enlace (LLC e MAC) | Não* | Boletim de Questões - Concurso Público UFPA, Edital nº 72/2015 - Analista de Tecnologia da Informação (Nível E), Área: Suporte de Redes (questão 35) — Universidade Federal do Pará (UFPA) | [ceps.ufpa.br](https://ceps.ufpa.br/legado/arquivos/concurso_publico/ufpa2015/Provas/Nivel%20E/PROVA%20DE%20ANALISTA%20DE%20TECNOLOGIA%20DA%20INFORMACAO%20-%20Area-SUPORTE%20DE%20REDES%20-%20Nivel%20E.pdf) | 2026-09-26 |
| `so_d09` | Redes e interconexão - roteamento (roteador e métrica RIP) | Não* | Boletim de Questões - Concurso Público UFPA, Edital nº 72/2015 - Analista de Tecnologia da Informação (Nível E), Área: Suporte de Redes (questão 31) — Universidade Federal do Pará (UFPA) | [ceps.ufpa.br](https://ceps.ufpa.br/legado/arquivos/concurso_publico/ufpa2015/Provas/Nivel%20E/PROVA%20DE%20ANALISTA%20DE%20TECNOLOGIA%20DA%20INFORMACAO%20-%20Area-SUPORTE%20DE%20REDES%20-%20Nivel%20E.pdf) | 2026-09-26 |
| `so_d10` | Sistemas de arquivos - NTFS/ext4, journaling e diretórios | Não* | Boletim de Prova - Concurso Público UNIFAP, Edital nº 01/2026 - Técnico de Laboratório (Ciências da Computação), questão 48 — Universidade Federal do Amapá (UNIFAP) | [arquivos.qconcursos.com](https://arquivos.qconcursos.com/prova/arquivo_prova/155128/depsec-2026-unifap-tecnico-de-laboratorio-ciencias-da-computacao-prova.pdf) | 2026-09-26 |
| `so_d11` | Sistemas de arquivos - i-nodes, blocos indiretos e tamanho máximo de arquivo | Não* | INF09344/INF02780 - Sistemas Operacionais - 3ª Lista de Exercícios (questão 19, alínea a) — Universidade Federal do Espírito Santo (UFES) | [www.inf.ufes.br](https://www.inf.ufes.br/~zegonc/material/Sistemas_Operacionais/so-lista3.pdf) | 2026-09-26 |
| `so_d12` | Sistemas de arquivos - arquivos e blocos em disco | Sim | Avaliação MP2 - Sistemas Operacionais - Gabarito Comentado (questão I) - Turma 2008.1, curso TADS — Universidade do Tocantins (UNITINS) | [www.unitins.br](https://www.unitins.br/BibliotecaMidia/Files/Documento/BM_633586197231398750tads___sistemas_operacionais___gabarito_comentado_a4_a5_a6_a7___2008.2.pdf) | 2026-09-26 |

## Resumo estatístico

- Total de questões: **50**
- Fontes distintas (domínios): **21**
- Gabaritos publicados pela própria fonte: **8**; determinados tecnicamente: **42** (marcados com * na tabela)
- Tipos de fonte: Blog/artigo especializado com questões e gabarito (3), Prova/lista de disciplina universitária (16), Questão de concurso público (banco de questões online) (31)

### Distribuição por domínio

| Domínio | Questões |
|---------|----------|
| www.qconcursos.com | 9 |
| www.questoesestrategicas.com.br | 8 |
| www.inf.ufrgs.br | 5 |
| www.inf.ufes.br | 4 |
| blog.grancursosonline.com.br | 2 |
| groups.ist.utl.pt | 2 |
| www.macedo.ufba.br | 2 |
| ifrs.edu.br | 2 |
| cdn.cebraspe.org.br | 2 |
| apcf.org.br | 2 |
| ceps.ufpa.br | 2 |
| www.eletrica.ufpr.br | 1 |
| ic.unicamp.br | 1 |
| www.pciconcursos.com.br | 1 |
| www.estudegratis.com.br | 1 |
| didata.ai | 1 |
| gabarite.com.br | 1 |
| www.estrategiaconcursos.com.br | 1 |
| conhecimento.fgv.br | 1 |
| arquivos.qconcursos.com | 1 |
| www.unitins.br | 1 |

## Como citar

Cada questão deve ser citada individualmente no TCC/artigo, seguindo ABNT
(NBR 10520) conforme o tipo da fonte:

- **Prova de disciplina / repositório institucional:**
  SOBRENOME, Nome. *Título da prova ou do documento*. Disciplina/Instituição,
  ano. Disponível em: URL. Acesso em: 26 set. 2026.
- **Prova de concurso público:**
  BANCA. *Prova — Cargo/Órgão*. Concurso, ano. Disponível em: URL.
  Acesso em: 26 set. 2026.
- **Apostila / material didático oficial:**
  AUTOR. *Título da apostila*. Instituição, ano. Disponível em: URL.
  Acesso em: 26 set. 2026.

No texto, cite a questão pelo ID (ex.: questão `so_c03`) acompanhado da
referência completa, e registre na lista de referências final. A tabela
"Fontes das questões do banco" no README gerado pelo teste espelha este
documento.
