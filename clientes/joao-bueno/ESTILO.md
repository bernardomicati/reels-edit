# João Bueno: guia de estilo dos Reels

Baseado na análise do vídeo de referência "Você acorda cansada…" (32,7 s, 720x1280, 30 fps).

## Regras do cliente (prioridade máxima)
- **3 variações de gancho por vídeo.** O corpo é o mesmo e muda só o gancho (`--gancho 1|2|3` ou `--todos`).
- **SEMPRE começar com uma imagem de insert** (B-roll no frame 0). O `reel.py` recusa renderizar sem isso.
- **Vídeo dinâmico, com bastante insert:** buscar cobertura de B-roll alta, trocando de imagem a cada 2–3 s.
- **Sem zoom** em nenhum momento: nada de punch-in nem de zoom nos cortes.
- **Fonte: Montserrat Bold.**

## Formato
- Vertical 9:16. Exportamos em 1080x1920 a 30 fps.
- Duração de 30 a 35 s, com fala corrida do começo ao fim e sem respiros longos (nenhum silêncio acima de 0,25 s).

## Estrutura do roteiro (copy)
1. **Gancho de identificação (0–7 s):** descreve a dor da paciente em 2ª pessoa.
   *"Você acorda cansada, sem disposição, e à noite, mesmo exausta, não consegue dormir."*
2. **Autoridade (7–13 s):** *"Essa é uma das frases que mais ouço no consultório. A paciente já procurou ajuda, o médico olhou os exames e disse que estava tudo normal."*
3. **Agravamento (13–29 s):** lista rápida de sintomas.
   *"Sem dormir bem, sem energia, sem vontade… isso começa a pesar também: irritação aumenta, a angústia aparece, os pensamentos mais negativos."*
4. **Virada/fechamento (29–32 s):** *"Um exame de rotina não conta a história inteira."*

## Talking head
- Plano médio-fechado, câmera na altura dos olhos (celular), com blazer azul-marinho, camiseta preta e pin.
- **Dois cenários** intercalados: escritório com estante de madeira e cortina escura, e sala clara com luminárias douradas.
- **Jump cuts secos** a cada 1,5–3 s, sem transição e **sem zoom**.
- Ele segura folhas de exame em alguns trechos, que funcionam como prop da fala sobre os exames.
- Gestos de mão entram na frente da câmera e reforçam o ritmo.

## B-roll (assinatura visual)
- O B-roll **não cobre a tela inteira**. Fica numa **faixa no topo, com ~30% da altura**, por cima da cabeça dele.
- A borda inferior da faixa é **esfumada/desfocada**, como se dissolvesse no cenário de trás.
- O apresentador continua sempre visível embaixo. A faixa aparece em ~70% do vídeo e troca de cena a cada 2–4 s.
- Conteúdo do B-roll: banco de imagens de mulheres cansadas, estressadas, com dor de cabeça ou deitadas na cama, ilustrando literalmente a frase falada.
- Fica sem B-roll principalmente no bloco de autoridade ("frases que mais ouço no consultório"), para dar foco no rosto.

## Legendas
- **Montserrat Bold**, **branca**, com sombra/contorno sutil escuro. Sem caixa e sem cor de destaque.
- **Pequenas e discretas**: ~5% da largura por letra, centralizadas, a **~80% da altura** (na altura do peito).
- **1 a 3 palavras por vez**, trocando no ritmo da fala, com caixa normal (não CAIXA ALTA) e mantendo a pontuação ("cansada," / "dormir.").

## Áudio
- Voz direta do celular, limpa e bem alta (pico −2,6 dB, média −24,6 dB). Normalizamos para −14 LUFS (padrão do Instagram).

## Parâmetros no `tools/reel.py`
| Parâmetro | Valor |
|---|---|
| `broll_band` | 0,31 (31% da altura) |
| `broll_feather` | 70 px de degradê |
| `font` / `font_size` | Montserrat Bold / 64 (em 1080x1920) |
| `caption_y` | 0,80 |
| `zoom` | 1,0 (sem zoom) |
| `lufs` | −14 |
