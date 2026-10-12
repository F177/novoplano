# Decisões

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
