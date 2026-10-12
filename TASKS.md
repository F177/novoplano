# TASKS.md

Backlog em ordem de execução. Cada tarefa é uma sessão de Claude Code e um PR.

**Legenda de execução:**
- 🤖 = Claude Code faz bem sozinho
- 🤝 = Claude Code escreve, você valida ouvindo ou medindo
- 👤 = faça à mão; é julgamento, não código

**Regras:**
- Não comece a próxima tarefa antes dos critérios de aceite da atual passarem.
- Diff acima de ~400 linhas: a tarefa estava mal fatiada. Pare e quebre.
- Toda escolha de modelo vai para `docs/decisoes.md` com os números que a justificam.
- Todo modelo ou dataset passa por `docs/licencas.md` antes de ser testado.
- Diga o custo de GPU antes de rodar. Desligue o Pod ao fim da sessão.

---

## Fase 0 — Repo novo (2 a 3 dias)

Objetivo: base limpa, com o que funcionava no repo anterior e nada do que não funcionava.

### T0.1 — Scaffold e porte seletivo 🤖
Estrutura conforme `CLAUDE.md`, `pyproject.toml` (ruff, pytest), `Makefile`, `.env.example`, CI no GitHub Actions rodando lint e test.

Porte do repo anterior (`F177/novoaudio@6e56281`), cada arquivo com os seus testes:
- `packages/ptbr/normalize.py`, `packages/ptbr/syllables.py`
- `packages/pipeline/subtitles.py`, `scorecard.py`, `report.py` (adaptados ao tipo `Line`)
- `scripts/r2.py`, `scripts/pod_runner.py` (com o fix de upload que apaga o destino remoto). `scripts/listen.py` foi para a T0.4: depende da máquina do `/ciclo` e do formato de segmentos do `dub.py` antigo.
- `evals/` inteiro: `golden/`, `languages/`, `taxonomy.json`, `human_labels/`, `calibration/`, `ledger.md`
- `.claude/` inteiro (agents, hooks, `skills/ciclo`), sem alterar a lógica; a adaptação é a T3.2

Não porte: nada de MOSS, OPUS-MT, Demucs, `segmentation.py`, `budget.py`, `prosody.py`, `synthesis.py`, `translation.py`, `pod_worker.py`, `dub.py`, `runpod/`.

**Aceite:** `make lint && make test` verde. `grep -ri "moss\|opus-mt\|demucs\|MIN_SYNTHESIS_SECONDS"` em `packages/` e `scripts/` volta vazio. README de uma linha apontando o repo anterior como referência congelada.

### T0.2 — Excluido, passse para o 50.3


### T0.3 — Conjunto Shorts-40, começando pelos 20 de dev 👤
`evals/sets/shorts40.json`: por Short, id, fonte, estrato, número de locutores, velocidade de fala, nível de música, sotaque, split.

Estratos para os 40: entrevista/podcast 6, streamer/gaming 5, reação/comentário 5, comédia/meme 5, educação/motivação 5, entrevista de rua 4, casos extremos 4 (menos de 5 s de fala, discussão com sobreposição, sussurro ou grito), esportes 3, vlog com música 3.

**Aceite:** 20 Shorts de dev com direito registrado, incluindo os 5 já rotulados. Pelo menos 8 com dois ou mais locutores e 6 rápidos. Holdout e exame podem ser completados até o Portão 1.

### T0.4 — Escuta cega em pares 🤖
`scripts/listen.py`, escrito do zero sobre Short e `Line` (o do repo anterior serve só de referência para o servidor local e a página), com o modo `pares`: duas versões do mesmo Short em ordem aleatória, nomes escondidos, um par duplicado oculto por sessão, rótulos em JSONL (preferido ou empate, "publicaria" sim/não, e para o pior lado a fala e uma classe de motivo da `taxonomy.json`). `scripts/sign_test.py` aplica a regra 15 de 20.

**Aceite:** testes do sorteio, do par duplicado e da regra (15/20 → vence, 12–14 → inconclusivo, empates excluídos). Uma sessão de 20 pares cabe em 40 minutos no celular.

### T0.5 — Ambiente de GPU 🤝
`scripts/pod_setup.sh` monta três venvs com versões fixadas: `asr`, `llm` (vLLM) e `tts`. `workers/__main__.py` com um subcomando por etapa, inicialmente só `smoke`.

**Aceite:** num Pod A40 novo, o script monta tudo do zero sem intervenção. Smoke test por venv: um ASR curto, um prompt no vLLM, uma frase no TTS. Tempo de setup e versões anotados no script.

---

## Fase 1 — Escolher modelos pelo ouvido (semanas 1 e 2)

Objetivo: saber se o 0 de 5 vem do roteiro ou da voz, e escolher o LLM e o TTS com números.

### T1.1 — Falas e janelas 🤖
`packages/pipeline/lines.py`: de palavras com tempos e locutores para `Line` (pydantic): `id`, `speaker`, `start`, `end`, `window_start`, `window_end`, `source_text`, `words`. A fala se fecha em fim de frase ou troca de turno; não existe duração mínima nem fusão por duração. A janela vai até o início da próxima fala que bloqueia (mesmo locutor ou outro locutor sem pausa).

**Aceite:** fixtures sintéticas: diálogo A/B/A ("Are you ready?" / "Yes." / "Then let's go") vira 3 falas com "Yes." em B. Nenhuma fala atravessa troca de locutor. Testes das janelas com e sem pausa entre falas.

### T1.2 — Roteiro com LLM aberto 🤝
`packages/pipeline/script.py` (prompt, esquema JSON, validação, reparo) e `workers/script_llm.py` (vLLM). Entrada: o Short inteiro em falas, com locutor, duração da janela e lista de nomes próprios. Saída por fala: três variantes pt-BR (curta, normal, solta) com sílabas estimadas por `packages/ptbr/syllables.py`, notas de entrega e marcas de "manter original" (nomes, interjeições). Regras no prompt e no perfil do idioma: pt-BR falado ("tá", "pra"), sem abreviação de chat, palavrão nunca suavizado, sem pt-PT.

Rode Gemma 4 31B e Qwen3.6/3.8-27B (quantizados para caber em 48 GB) nos 20 Shorts de dev.

**Aceite:** 100% de JSON válido depois de no máximo um reparo. Zero caractere CJK. Nomes próprios da lista preservados em todas as variantes. Teste com 10 frases de palavrão: nenhuma suavizada. Tempo e GPU por Short anotados.

### T1.3 — Teste cego de roteiro 👤
Leia os roteiros contra o vídeo original, sem saber a origem: LLM A × OPUS-MT, LLM B × OPUS-MT, A × B. As traduções OPUS-MT vêm do repo anterior.

**Aceite:** modelo de roteiro escolhido pela regra 15 de 20 e registrado em `docs/decisoes.md`. Se nenhum LLM vencer o OPUS-MT, pare e me avise antes de seguir.

### T1.4 — Biblioteca de vozes v0 🤝
`scripts/voice_library.py`: cria vozes com Qwen3-TTS VoiceDesign a partir de descrições, gera as referências de estilo `neutro`, `animado` e `intenso`, calcula F0 médio e embedding (ECAPA) e grava `assets/voices/library/<voice_id>/meta.json` + `refs/<estilo>.wav`. Oito vozes: 4 masculinas, 4 femininas, faixas jovem e adulta.

**Aceite:** você aprova cada voz de ouvido (sotaque brasileiro, natural, sem chiado). Para toda voz, a similaridade ECAPA entre os próprios estilos é maior que a similaridade com qualquer outra voz. `meta.json` completo, com modelo, revisão e prompt de criação.

### T1.5 — Bake-off de TTS 🤝
Mesmo roteiro (T1.3) e mesmas vozes (T1.4) em Qwen3-TTS-12Hz-1.7B-Base e Chatterbox Multilingual V3 pt-BR. MOSS só como controle, usando os áudios do repo anterior. Por modelo, medir: CER round-trip, UTMOSv2, previsibilidade de duração (variação da duração para o mesmo texto), taxa de falha em falas de 1 e 2 palavras, segundos de GPU por fala. Depois, 20 pares cegos entre os dois candidatos.

**Aceite:** tabela por modelo em `docs/decisoes.md` e TTS escolhido pela regra 15 de 20. Empate: fica o mais rápido e mais estável em duração.

### T1.6 — Experimento 2×2 🤝
Monte quatro versões dos 20 Shorts de dev: {OPUS-MT, LLM escolhido} × {voz MOSS do banco antigo, TTS escolhido + biblioteca}. Os braços antigos vêm do repo anterior rodado sem alterações; a montagem nova usa uma mixagem provisória com stretch limitado a ±12% e sem corte. Pares cegos: cada versão nova contra a atual. Rotule "publicaria" em todas.

**Aceite:** memorando de uma página em `docs/` dizendo qual fator explica a maior parte dos "não publicaria", com os números. A ordem da Fase 2 é revista à luz do memorando.

### 🚦 Decisão 1
LLM de roteiro e TTS escolhidos, fonte dominante de falha conhecida. Só então siga para a Fase 2.

---

## Fase 2 — Pipeline base (semanas 2 a 4)

Objetivo: as 13 etapas rodando de ponta a ponta, em lote, sem intervenção.

### T2.1 — Separação RoFormer 🤝
`workers/separate.py` com Mel-Band RoFormer. Compare com `htdemucs` nos 20 de dev: vazamento de inglês no stem M&E (ASR sobre o M&E encontra palavras?) e escuta de 5 Shorts.

**Aceite:** menos palavras vazadas que o `htdemucs` no total do dev. Sua escuta confirma.

### T2.2 — ASR, diarização e flags 🤝
`workers/transcribe.py` (Parakeet-TDT-0.6B-v3, com WhisperX como segunda opinião) e `workers/diarize.py` (pyannote Community-1), ambos sobre o stem de diálogo. Flags: discordância entre os dois ASR acima de um limiar, palavra dentro de silêncio do VAD (alucinação), sobreposição de fala.

**Aceite:** roda nos 20 de dev. Cada flag tem teste positivo e negativo com fixture sintética. Limiares marcados "não calibrado".

### T2.3 — Casting automático 🤖
`packages/pipeline/casting.py`: atributos por locutor (gênero estimado, F0, energia) → voz da biblioteca. Dois locutores do mesmo Short nunca recebem a mesma voz. Elenco persistido por canal e reaproveitado.

**Aceite:** testes: Short de dois locutores → duas vozes distintas; mesmo canal em dois Shorts → mesmo elenco; troca manual sobrescreve e persiste.

### T2.4 — Tags de percepção e estilo por fala 🤝
`workers/perceive.py`: emoção e intensidade (emotion2vec, se a licença passar na T0.2) e não-verbais (riso, grito, respiração) por fala. `casting.py` escolhe a referência de estilo da voz por fala a partir das tags. Não-verbais são marcados para manter o áudio original na mixagem.

**Aceite:** tags em todas as falas do dev. Você confere 30 falas: estilo escolhido condiz com o original em pelo menos 2 de cada 3.

### T2.5 — Síntese em lote com candidatos 🤝
`workers/synthesize.py`: por fala, as variantes do roteiro × 2–3 candidatos, em lote, com a referência de estilo do casting. Falas de 1–2 palavras são sintetizadas no contexto da vizinha e recortadas, ou mantidas como interjeição original quando marcadas.

**Aceite:** segundos de GPU por Short anotados. Em 20 falas de 1–2 palavras, nenhuma degenera (CER e escuta).

### T2.6 — Crítico v1 🤖
`packages/pipeline/critic.py`: agrega CER round-trip, ajuste à janela, similaridade com a voz da biblioteca, UTMOSv2, ID de idioma (pt e não en), nível e clipping. Escolhe o melhor; até 2 regenerações com variante mais curta; depois, flag para revisão.

**Aceite:** testes unitários com sinais sintéticos. Teste de mutação: áudio cortado no meio, ruído forte e frase colada duas vezes disparam as flags certas.

### T2.7 — Solver de timing 🤖
`packages/pipeline/timing.py`: posiciona todas as falas do Short de uma vez. Restrições: ordem preservada, sem sobreposição do mesmo locutor, janela respeitada, stretch ≤ ±12% (rubberband com preservação de formantes). Inviável → pede a variante curta → flag.

**Aceite:** testes de propriedade: nunca há sobreposição do mesmo locutor, nunca há corte, ordem sempre preservada. Zero segundo de fala cortada nos fixtures, incluindo diálogo rápido de três trocas por segundo.

### T2.8 — Mixagem com ambiência e marca d'água 🤝
`packages/pipeline/mix.py` + `workers/watermark.py`: nível casado com o original por locutor, EQ e reverb estimados do stem de diálogo, não-verbais originais restaurados, M&E por baixo, −14 LUFS e −1 dBTP. Marca d'água inaudível em todo áudio gerado.

**Aceite:** testes de loudness e pico. Marca detectável depois da recompressão AAC do remux. Sua escuta em 5 Shorts: sem inglês no fundo, sem clique nas bordas, a voz parece estar na mesma sala.

### T2.9 — CLI ponta a ponta, em lote 🤝
`scripts/dub.py <pasta>`: roda cada etapa para N Shorts por carregamento de modelo, com cache por hash e `--force-stage`. `report.json` por fala com todos os sinais, o elenco, a variante e o candidato escolhidos. Tempo e segundos de GPU por etapa.

**Aceite:** 50 execuções seguidas sem job falho. Zero segundo de fala cortada. No máximo US$ 0,15 de GPU por Short de 60 s, calculado pelo preço do RunPod Serverless.

### 🚦 Portão 1
Pelo menos 50% dos 20 Shorts de dev publicáveis, pelo seu rótulo. Se falhar, ataque o motivo que mais aparece nos rótulos, não o que a métrica automática aponta.

---

## Fase 3 — Qualidade (semanas 5 a 10)

Objetivo: 70% publicáveis no holdout. Cada mudança passa pela regra 15 de 20.

### T3.1 — Rotulagem por fala e calibração do crítico 👤 + 🤖
Rotule cada fala do dev como `ok` ou `corrigiria`, com a classe do motivo. O scorecard calcula precisão e recall de cada flag e ajusta os pesos do crítico nesses rótulos.

**Aceite:** pelo menos 300 falas rotuladas. Tabela de precisão e recall por flag. Pesos novos com justificativa escrita.

### T3.2 — Ciclo de qualidade no pipeline novo 🤝
Adapte `/ciclo`, os agentes e `judge_packet` ao formato de `report.json` por fala. Mantenha splits, guarda de diff e revisor adversarial.

**Aceite:** `/ciclo avaliar` roda nos 20 de dev sem erro. Calibração do juiz refeita contra os rótulos da T3.1.

### T3.3 — LoRA pt-BR do TTS nas vozes da biblioteca 🤝
Fine-tune do TTS escolhido nas vozes da biblioteca, com áudio delas e corpora de licença comercial verificada (por exemplo Common Voice pt e MLS Portuguese, após checagem na T0.2). Estimativa: 20–60 horas de GPU, cerca de US$ 10–40 num A40.

**Aceite:** vence o modelo base pela regra 15 de 20. CER não piora. Custo real anotado.

### T3.4 — Estilos de emoção 🤝
Mais estilos por voz (por exemplo irritado, triste, sussurro, grito) e política de escolha por tag.

**Aceite:** vence a versão de três estilos pela regra 15 de 20.

### T3.5 — Falas curtas, interjeições e sobreposição 🤝
Política para sobreposição (dublar o locutor dominante e manter o resto do original atenuado) e para risos, gritos e interjeições.

**Aceite:** nos Shorts de dev com sobreposição, taxa de correção dessas falas cai. Vence pela regra 15 de 20.

### T3.6 — Glossário e elenco por canal 🤖
Termos do canal com tradução e pronúncia fixas, injetados no roteiro e no TTS.

**Aceite:** termo do glossário sai como definido em 10 Shorts de teste.

### 🚦 Portão 2
Pelo menos 70% dos 10 Shorts de holdout publicáveis, rotulados por você e por pelo menos um voluntário. Não construa produto web antes disso.

---

## Fase 4 — Produto (depois do Portão 2; a T4.3 pode começar depois do Portão 1)

### T4.1 — Schema e migrations 🤖
Tabelas com `org_id`: organizações, canais, elencos, vídeos, falas, revisões de fala, jobs, exportações, registros de autorização e de consentimento.
**Aceite:** migrations sobem e descem limpo. Seed de desenvolvimento.

### T4.2 — Fila em Postgres 🤖
Jobs por etapa com `FOR UPDATE SKIP LOCKED` e retomada pelo hash da etapa.
**Aceite:** 10 workers concorrentes nunca processam o mesmo job duas vezes. Job interrompido é retomado.

### T4.3 — RunPod Serverless 🤝
Três endpoints: `audio` (separação, ASR, diarização, percepção, crítico), `llm` (vLLM) e `tts`. Lote por carregamento de modelo.
**Aceite:** nenhuma lógica de modelo duplicada entre `workers/` e os handlers. Um lote de 10 Shorts de ponta a ponta. Cold start e custo por Short anotados em `runpod/README.md`.

### T4.4 — Auth, upload e declaração de autorização 🤖
**Aceite:** upload de 1 GB sem estourar memória da API. Declaração de autorização do criador gravada com timestamp.

### T4.5 — Endpoints REST 🤖
**Aceite:** testes de integração por rota, incluindo isolamento por `org_id`.

### T4.6 — Revisão rápida 🤖
Tela por Short: tocar original e dublado, aceitar, regenerar uma fala, trocar a voz de um locutor, rejeitar. Cada ação cria revisão.
**Aceite:** três pessoas de fora revisam 10 Shorts sozinhas, sem instrução. Taxas de aceitar, regenerar e rejeitar gravadas por fala.

### T4.7 — Export com marca obrigatória 🤖
**Aceite:** teste garantindo que nenhum caminho de export pula a marca d'água. Rótulo de IA no export. Registro de exportação com `org_id`.

### T4.8 — Custos e observabilidade 🤖
Sentry e painel de custo e latência por Short e por etapa.
**Aceite:** custo por Short visível para cada lote.

### T4.9 — Planos e cobrança 🤖
Asaas (PIX e boleto).

---

## Fase 5 — Vantagens próprias (mês 3 em diante)

### T5.1 — Reranker aprendido 🤝
Treinado nos seus rótulos e nas ações da revisão rápida (pelo menos ~2.000 falas).
**Aceite:** vence o crítico com pesos manuais pela regra 15 de 20.

### T5.2 — Preditor de duração pt-BR 🤖
Texto + voz + estilo → segundos, treinado no próprio áudio sintetizado.
**Aceite:** cerca de 30% menos regenerações por Short com qualidade igual.

### T5.3 — LoRA do LLM de roteiro com as edições 🤝
**Aceite:** depois de ~2.000 falas editadas, vence o modelo base pela regra 15 de 20.

### T5.4 — Vozes gravadas sob contrato 👤
Substituir as vozes mais usadas da biblioteca por vozes de pessoas reais, com contrato de cessão para síntese, 1–2 horas de gravação por voz e LoRA por voz.
**Aceite:** cada voz nova vence a voz desenhada que substitui pela regra 15 de 20.

### T5.5 — (Opcional, só com decisão explícita) Clonagem da voz original
Feature premium, só com consentimento registrado do dono da voz.

### T5.6 — (Opcional, só com decisão explícita) Lip-sync
Só para rostos frontais, com teste A/B contra o vídeo sem lip-sync.

---

## Como conduzir as sessões

- Abra cada sessão com: "Leia CLAUDE.md e a tarefa Tx.y do TASKS.md. Releia o aceite e me diga o plano antes de codar."
- Tarefas 🤝 terminam com um comando que você roda e um áudio ou tabela para você julgar.
- Ao fechar uma tarefa: `make lint && make test`, commit no padrão, decisão em `docs/decisoes.md` quando houver escolha.
- Se o aceite exigir GPU, o custo estimado vem antes da execução.
