# CLAUDE.md

Contexto permanente do projeto. Leia antes de qualquer tarefa.

## O que é este projeto

SaaS de dublagem automática **em lote de YouTube Shorts e Reels**, inglês → português brasileiro. O usuário principal é o **clipper**: recorta e reposta clipes de criadores, com autorização do criador, para levar o conteúdo ao público brasileiro.

O clipper sobe muitos Shorts de uma vez, o sistema dubla tudo automaticamente e uma **revisão rápida** permite aceitar, regenerar uma fala, trocar a voz ou rejeitar cada Short antes de exportar. O produto precisa sair **bom sem edição** na maioria dos casos.

O que define "bom", em ordem:

1. Tradução certa e natural em pt-BR **falado**: sentido, humor, gíria e tom do original. Palavrão, gíria e tom saem como no original, sem suavizar.
2. Timing: nenhuma fala cortada, nada apressado nem esticado de forma audível, mesmo em diálogo rápido com troca de locutor.
3. Voz pt-BR natural, com a energia e a emoção do original.
4. Voz do criador clonada: **feature futura e opcional**, não requisito. O padrão é uma **biblioteca de vozes próprias** (elenco).

Fala rápida, curta e cheia de troca de locutor é o caso **principal**, não um caso de borda. Custo de GPU por Short importa tanto quanto qualidade.

Fundador solo. Prioridade absoluta: **simplicidade operacional e custo zero em ociosidade**.

Repositório anterior: `F177/novoaudio`, congelado no commit `6e56281`. Serve só como referência e fonte dos achados listados abaixo. Nunca importe código de lá fora de uma tarefa do `TASKS.md`.

## Decisões registradas

Toda decisão nova entra em `docs/decisoes.md` com data, alternativas e evidência.

- **2026-10-10 — Geração 100% in-house.** Nenhuma API externa nem serviço pago de terceiros no caminho de geração (ASR, tradução, TTS, avaliação de produto). Só modelos open-weight rodando na nossa GPU. ElevenLabs e similares são concorrentes.
- **2026-10-11 — Projeto novo.** O pipeline anterior (Demucs, OPUS-MT, MOSS-TTS, segmentação por pausa com piso de 3,2 s) foi descontinuado: 0 de 5 Shorts publicáveis na linha de base rotulada.
- **2026-10-11 — Voz por biblioteca.** Cada locutor recebe uma voz da biblioteca própria por casting automático. Clonagem do locutor original fica fora do escopo até decisão explícita.
- **2026-10-11 — A fala é a unidade.** Tradução, síntese e revisão acontecem por fala (linha de diálogo) com janela de tempo flexível, não por segmento delimitado por pausa.
- **2026-10-11 — Short inteiro de uma vez.** Um contexto de LLM por Short, um elenco por Short, um solver de timing por Short.
- **2026-10-12 — Licença não bloqueia, por enquanto.** O projeto é pessoal, privado e não comercial. Modelos e datasets com licença não comercial ou de pesquisa podem ser testados e adotados. A licença de cada um continua registrada, e antes de qualquer uso comercial todos os não comerciais são revistos e trocados.

## Invariantes de arquitetura (não viole sem me perguntar)

1. **A fala é a unidade atômica.** Toda operação de dublagem acontece no nível da fala. Nunca reprocesse um Short inteiro para corrigir uma fala.
2. **Nunca corte fala para caber.** A fala pode ocupar silêncio vizinho; se ainda não cabe, peça a variante mais curta do roteiro; se nem assim cabe, sinalize. Time-stretch no máximo ±12%, sempre com preservação de formantes.
3. **Toda etapa é um job idempotente e retomável**, chaveado pelo hash de entrada + parâmetros + versão do modelo. Separação, ASR e diarização rodam uma vez; refazer só com `--force-stage`.
4. **Nunca destrua a versão anterior de uma fala.** Edição cria revisão; o histórico é preservado.
5. **Editar uma fala não altera as vizinhas automaticamente.** Mostre o impacto, não conserte sozinho.
6. **`org_id` em toda tabela de domínio**, desde o primeiro dia. Toda query filtra por ele.
7. **Nada de GPU ociosa fora de uso ativo.** Produção em RunPod Serverless (cobrança por segundo, escala a zero). Desenvolvimento em Pod via SSH, desligado ao fim de cada sessão. Shorts são processados em lote por carregamento de modelo.
8. **Licença registrada, não bloqueante.** Todo modelo ou dataset adotado tem a licença anotada (nome, URL, comercial sim/não) na entrada de `docs/decisoes.md` que o adota. Não comercial é permitido enquanto o projeto for pessoal (decisão de 2026-10-12).
9. **Marca d'água em todo áudio gerado** antes de chegar a qualquer pessoa de fora. Nenhum caminho de export pula a marca.
10. **`packages/` é puro**: sem rede, sem banco, sem framework. Recebe dados, devolve dados, testável sem GPU.
11. **Idioma é dado** (`evals/languages/`, `evals/golden/en-<idioma>.json`, `TargetLanguage`). Nunca `if idioma == ...` em lógica compartilhada.

## Stack (travada — não substitua sem me perguntar)

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind, na Vercel |
| API | FastAPI (Python 3.12), em Railway |
| Banco / Auth | Supabase (Postgres + Auth) |
| Storage de mídia | Cloudflare R2 |
| GPU / workers de ML | RunPod Serverless em produção; Pod via SSH em desenvolvimento |
| Servidor de LLM | vLLM na nossa GPU |
| Fila | Postgres, `SELECT ... FOR UPDATE SKIP LOCKED` |
| Pagamento | Asaas (PIX e boleto) |
| Erros | Sentry |

**Não introduza:** Kubernetes, Airflow, Temporal, Celery, RabbitMQ, Kafka, microserviços, GraphQL, ORM pesado além do SQLAlchemy Core, serviço AWS com taxa de egresso, ou qualquer API de geração de terceiros.

**GPU:** classe 48 GB (A40 ou L40S). Nada de H100 nem LLM multi-GPU. Não use pods com partição MIG (bug de PyTorch/NVML visto no repo anterior).

## Pipeline (13 etapas)

Modelos marcados "candidato" ainda não foram validados; a escolha final sai das tarefas indicadas e vai para `docs/decisoes.md`.

| # | Etapa | Saída | Modelo | Licença | Status |
|---|---|---|---|---|---|
| 1 | Ingestão e sondagem | Áudio 48 kHz; proporção de fala, cortes de cena, rostos | ffmpeg + VAD | — | — |
| 2 | Separação | Stem de diálogo + stem de música e efeitos (M&E) | Mel-Band RoFormer vocals | MIT | Candidato (T2.1) |
| 3 | ASR e tempo por palavra | Palavras, tempos, confiança, risos | Parakeet-TDT-0.6B-v3; WhisperX large-v3 como segunda opinião | CC-BY-4.0; MIT | Candidato (T2.2) |
| 4 | Diarização | Locutor por palavra, sobreposições, embeddings | pyannote Community-1 | CC-BY-4.0 | Candidato (T2.2) |
| 5 | Tags de percepção | Emoção, intensidade, ênfase e não-verbais por fala | emotion2vec + detector de não-verbais | Verificar | Candidato (T2.4) |
| 6 | Roteiro | Por fala: 3 variantes pt-BR (curta, normal, solta), sílabas, notas de entrega | Gemma 4 31B ou Qwen3.6/3.8-27B, 8 ou 4 bits, via vLLM | Apache-2.0 | Decisão na T1.3 |
| 7 | Casting | Voz da biblioteca por locutor + referência de estilo por fala | `packages/pipeline/casting.py` | — | T2.3 |
| 8 | Síntese | 2–3 candidatos por fala | Qwen3-TTS-12Hz-1.7B-Base ou Chatterbox Multilingual V3 pt-BR | Apache-2.0; MIT | Decisão na T1.5 |
| 9 | Crítico | Melhor candidato por fala, ou flag | CER (Whisper), ajuste de duração, similaridade com a voz da biblioteca (ECAPA), UTMOSv2, ID de idioma | Verificar cada um | T2.6 |
| 10 | Solver de timing | Início e stretch por fala | `packages/pipeline/timing.py` | — | T2.7 |
| 11 | Mixagem e marca | Áudio final −14 LUFS, −1 dBTP, com marca d'água | Nível por locutor, ambiência casada, não-verbais originais restaurados | — | T2.8 |
| 12 | Lip-sync | — | Fora do escopo | — | — |
| 13 | Render e QA final | MP4 + pacote de revisão | ffmpeg; re-ASR do mix final contra o roteiro | — | T2.9 |

**Paralelo:** separação junto com sondagem de vídeo; ASR, diarização e tags no stem de diálogo; roteiro junto com casting; todas as falas × candidatos na síntese e no crítico. **Sequencial:** timing depois de todas as falas escolhidas; mix depois do timing; render por último.

**Licença não comercial ou que exige acordo (permitidos enquanto o projeto for pessoal; trocar antes de comercializar):** Fish Audio S2 Pro, pesos do Voxtral TTS, Hibiki-Zero, IndexTTS2/2.5, pesos do F5-TTS, XTTS-v2, pesos do Breeze TTS, AuK (pelo encoder Qwen2.5-Omni-3B).

## Biblioteca de vozes (elenco)

- **Origem das vozes, em ordem:** (a) vozes **desenhadas por modelo** (Qwen3-TTS VoiceDesign, Apache-2.0), sem pessoa real por trás; (b) mais tarde, vozes **gravadas por pessoas reais sob contrato** de cessão de voz para síntese, com escopo, remuneração e revogação. Nunca use a voz de uma pessoa real sem contrato.
- **Formato:** `assets/voices/library/<voice_id>/meta.json` + `refs/<estilo>.wav`. `meta.json` traz gênero percebido, faixa etária, F0 médio, embedding de timbre, energia, registro (casual, narração, hype), estilos disponíveis, origem e licença.
- **Estilos por voz:** pelo menos `neutro`, `animado` e `intenso`. Referência neutra puxa a entrega para o neutro (achado do repo anterior), então a emoção vem da referência de estilo escolhida por fala.
- **Casting:** cada locutor da diarização recebe uma voz por gênero, idade, F0, energia e tipo de conteúdo. Dois locutores do mesmo Short nunca recebem a mesma voz. O elenco de um canal é persistido e reaproveitado entre vídeos. O usuário pode trocar.
- **Tamanho inicial:** 8 vozes (4 masculinas, 4 femininas, duas faixas etárias). Cresce pelo uso real.
- **Fine-tune:** com biblioteca fixa, LoRA por voz é possível e é a principal alavanca de naturalidade (Fase 3).

## Avaliação de qualidade

- **Métrica de decisão:** preferência cega em pares de Shorts inteiros, julgada pelo fundador. Regra: excluindo empates, a versão nova precisa vencer **pelo menos 15 de 20** pares (teste do sinal unilateral, p ≈ 0,02). 12 a 14 vitórias é inconclusivo: só fica se for mais barato ou mais simples.
- **Portões:** taxa de publicação por rótulo humano. Portão 1: ≥ 50% no dev. Portão 2: ≥ 70% no holdout, rotulado pelo fundador e por pelo menos um voluntário. Nunca `any_flag_rate`.
- **Conjunto Shorts-40** (`evals/sets/shorts40.json`): 40 Shorts  splits dev 20 / holdout 10 / exame selado 10, estratificados por tipo de conteúdo, número de locutores, velocidade de fala, música e sotaque.
- **Métricas automáticas** servem para triagem e escolha de candidatos, nunca para decidir o que entra. Nunca use a mesma métrica para controlar e para medir.
- **Nunca ajuste um limiar contra um vídeo só.** Todos os limiares começam marcados como "não calibrado".
- Rótulos humanos em `evals/human_labels/` valem mais que qualquer juiz. O juiz por LLM (`/ciclo`) é ferramenta de desenvolvimento, fora do caminho de geração, nunca sobre upload de cliente.

## Achados herdados do repo anterior (medidos, não repita os erros)

- faster-whisper com `condition_on_previous_text=True` alucina repetição em áudio curto e limpo: use `False`.
- No ASR de avaliação, não decodifique com `repetition_penalty` nem `no_repeat_ngram_size`: isso cega a detecção de loop do TTS.
- Transferência de contorno de pitch por phase vocoder quase dobrou o CER: não use.
- Time-stretch de até 1,5× é audível: o teto agora é ±12%.
- Ordem do texto para o TTS: glossário/IPA → normalização → marcadores de pausa. Normalizar antes do glossário corrompe termos com dígito.
- O nível de fala varia por fala no TTS: iguale o nível ao do original antes de mixar.
- Trecho do ASR sem pontuação fez o tradutor inverter o sentido. Pedir pontuação ao Whisper via `initial_prompt` fez ele pular uma frase.
- LLM pequeno (Qwen2.5-7B) errou sentido e vazou caracteres chineses: teste vazamento de CJK em todo modelo de roteiro.
- Modelos derivam para pt-PT: imponha pt-BR no prompt e filtre formas pt-PT pelo perfil do idioma.
- Fala de uma palavra só degenerou no TTS anterior: teste falas de 1–2 palavras em todo TTS candidato.
- Cache por existência de arquivo reaproveitou tradução errada: chave por hash de entrada.
- Upload de diretório para o Pod aninhava pastas: apague o destino remoto antes de subir.
- WhisperX 3.8.6 renomeou `use_auth_token` para `token`.

## Ambiente de GPU (desenvolvimento)

- Pod A40 ou L40S via SSH, orquestrado por `scripts/dub.py` e `scripts/pod_runner.py`. Código de modelo em `workers/`, um módulo por etapa.
- Três venvs com versões fixadas por `scripts/pod_setup.sh`: `asr` (separação, ASR, diarização, percepção, crítico), `llm` (vLLM) e `tts`.
- Desligue o Pod ao fim de cada sessão. Se o Pod estiver inacessível, pare e me avise; não contorne.

## Layout do repositório

```
/apps
  /web              Next.js — revisão rápida e dashboard (Fase 4)
  /api              FastAPI — REST, auth, orquestração de jobs (Fase 4)
/packages
  /ptbr             normalize.py, syllables.py (portados do repo anterior)
  /pipeline         Lógica pura
    lines.py          Falas e janelas a partir de ASR + diarização
    script.py         Prompt, esquema JSON, validação e reparo do roteiro
    casting.py        Voz por locutor e estilo por fala
    critic.py         Agregação de sinais e escolha de candidato
    timing.py         Solver global de timing
    mix.py            Nível, ambiência, não-verbais, loudness
    subtitles.py      Legenda pt-BR (SRT)
    scorecard.py      Agregação por Short
    report.py         Relatório local
/workers            Código de modelo, um módulo por etapa: separate, transcribe,
                    diarize, perceive, script_llm, synthesize, evaluate, watermark
/scripts            dub.py, listen.py, voice_library.py, pod_runner.py, pod_setup.sh,
                    r2.py, eval_*.py
/assets/voices/library   Biblioteca de vozes
/evals              golden, languages, taxonomy, human_labels, calibration, sets, ledger.md
/docs               decisoes.md
/migrations         SQL versionado
/runpod             Endpoints Serverless: audio, llm, tts (Fase 4)
/.claude            agents, hooks, skills/ciclo
```

## Comandos

```bash
make dev          # sobe api + web local
make test         # pytest + vitest
make lint         # ruff + eslint + tsc --noEmit
make migrate      # aplica migrations
make eval         # harness de avaliação
make pipeline-cli VIDEO=path/to.mp4   # pipeline completo
```

Antes de dizer que uma tarefa está pronta, rode `make lint && make test`.

## Conformidade (obrigatório, não é backlog)

- Todo upload exige declaração de que o usuário tem autorização do criador para o conteúdo. Persista o registro com timestamp.
- Vozes da biblioteca gravadas por pessoas reais exigem contrato assinado e registrado. Vozes desenhadas por modelo registram o modelo, a versão e o prompt de criação.
- Voz pode ser dado pessoal sensível (LGPD art. 5º, II). Defina retenção e permita exclusão.
- Marca d'água de conteúdo sintético em todo áudio gerado e rótulo de IA no export (EU AI Act art. 50, vigente desde 2/8/2026).
- Nunca logue conteúdo de vídeo do cliente em serviços de terceiros.

## O que NÃO construir

Estas coisas vão parecer urgentes. Não são. Não implemente sem eu pedir explicitamente:

- Clonagem da voz do locutor original
- Lip-sync facial / manipulação de vídeo
- Dublagem ao vivo ou streaming
- Outros pares de idiomas além de EN → pt-BR
- Editor detalhado por fala antes do Portão 2 (só revisão rápida)
- App mobile, API pública, webhooks, integrações
- Gestão de times, papéis, permissões granulares
- Treino de modelo grande, modelo de áudio-linguagem próprio, ou qualquer treino com filmes e dublagens sem licença
- Dashboard de analytics além do básico

## Convenções

- Python: ruff (linha 100), type hints obrigatórios em funções públicas, pydantic nas fronteiras de dados (a `Line` é o tipo central).
- TypeScript: strict. Sem `any`. Sem `!` non-null assertion.
- SQL escrito à mão em migrations numeradas.
- Toda função de `packages/` tem teste unitário com dado sintético, sem GPU.
- Toda chamada de modelo grava nome, revisão e parâmetros no metadado do job.
- Commits: imperativo, em inglês, escopo prefixado — `pipeline: add global timing solver`. Um commit por tarefa.
- Nomes de domínio em inglês no código; conteúdo pt-BR só em dados e UI.

## Glossário de domínio

- **Fala** — linha de diálogo de um locutor, delimitada por frase ou turno. Unidade de roteiro, síntese, revisão e edição.
- **Janela** — intervalo em que a fala dublada pode tocar: o tempo original mais o silêncio vizinho disponível.
- **Variante** — versão do roteiro de uma fala: curta, normal ou solta.
- **Elenco** — mapa locutor → voz da biblioteca de um Short ou canal.
- **Referência de estilo** — áudio de uma voz da biblioteca num estilo (neutro, animado, intenso) que guia a entrega.
- **Crítico** — pontuação automática de cada candidato.
- **Stem M&E** — música e efeitos sem a fala original.
- **Taxa de publicação** — fração dos Shorts que um humano publicaria sem edição. Métrica dos portões.
- **Taxa de correção** — fração das falas que um humano corrigiria. Diz onde investir.
- **Clipper** — usuário principal: publica Shorts em volume, com autorização do criador.

## Como trabalhar comigo

- Tarefa por vez, seguindo `TASKS.md` na ordem. Releia os critérios de aceite antes de começar.
- Se uma tarefa parecer exigir violar um invariante, pare e pergunte.
- Se precisar de uma decisão de produto que não está aqui, pergunte; não invente.
- Não refatore fora do escopo da tarefa atual.
- Diga o custo de GPU antes de gastar.
- `/ciclo` (avaliar → calibrar → planejar → implementar → revisar → verificar) volta a valer a partir da T3.2. Não edite `evals/`, `.claude/hooks/` nem limiares para fazer um ciclo passar.
