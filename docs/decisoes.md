# Decisões

## 2026-10-12 — Licença não bloqueia enquanto o projeto for pessoal

**Contexto.** O projeto é pessoal, privado e não comercial. A regra anterior (só licença
comercial verificada) excluía modelos que podem ser os melhores para a qualidade.

**Decisão.** Modelos e datasets com licença não comercial, de pesquisa ou que exigem acordo podem
ser testados e adotados. Cada adoção registra aqui o nome da licença, a URL e se permite uso
comercial.

**Alternativas.** Manter só licenças comerciais desde já: descartada pelo fundador para não
limitar a qualidade numa fase sem receita.

**Gatilho de revisão.** Antes de qualquer uso comercial, todo componente marcado "comercial: não"
é trocado ou licenciado. Conhecidos hoje: Fish Audio S2 Pro, pesos do Voxtral TTS, Hibiki-Zero,
IndexTTS2/2.5, pesos do F5-TTS, XTTS-v2, pesos do Breeze TTS (BreezeBlue Research and
Non-Commercial License) e AuK, que carrega o encoder Qwen2.5-Omni-3B (Qwen Research License
Agreement, cláusula 2(a): "FOR NON-COMMERCIAL PURPOSES ONLY").

## 2026-10-12 — Legenda embutida é recurso adicional, não fonte de verdade

**Contexto.** 29 dos 40 Shorts do conjunto Shorts-40 têm a fala legendada no próprio vídeo
(amostra de 4 quadros por Short). Os de bodycam rotulam o locutor ("Officer:", "Father:").

**Decisão.** O texto da legenda, lido por OCR open-weight, entra como segunda opinião ao lado do
ASR: grafia de nomes, pontuação e fim de frase, rótulo de locutor, ênfase. O ASR continua dono
das palavras e dos tempos. Sem legenda, o pipeline funciona igual.

**Alternativas.** (1) Ignorar a legenda. (2) Usar a legenda como transcrição principal.
Descartada a (2): há legenda censurada ("F\*CK", "BULLSH\*T") com áudio sem censura, o que
suavizaria palavrão; há texto que não é fala (títulos, placar, HUD, letra de música); a legenda
mostra 1 a 3 palavras por vez, com tempo grosseiro; e muitas legendas são geradas por ASR, com
erros próprios.

**Evidência.** Amostra visual dos 40 Shorts em 2026-10-12. Ganho ainda não medido: depende do
ASR da T2.2 para comparar.

**Em aberto.** O que fazer com a legenda em inglês que continua no vídeo dublado.
