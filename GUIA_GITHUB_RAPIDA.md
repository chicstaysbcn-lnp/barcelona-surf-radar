# Publicar Barcelona Surf Radar desde GitHub.com (sin terminal)

## Paso 1: repositorio
- GitHub.com > New repository > `barcelona-surf-radar`.
- Public, sin README, sin .gitignore y sin licencia inicial. Create repository.

## Paso 2: subir archivos
- Extraer ZIP en el ordenador. NO subir el ZIP ni meter todo en una subcarpeta.
- En el repositorio: Add file > Upload files.
- Arrastrar el **contenido** de la carpeta, excepto `.github` si el navegador bloquea las carpetas ocultas.
- Comprobar que `index.html` esté en la raíz y que existan `data/spot_profiles.json`, `scripts/forecast.py`, etc.
- Commit changes.

## Paso 3: subir workflow (.github)
- Repositorio: Add file > Create new file.
- Escribir como nombre: `.github/workflows/surf-radar.yml`
- Copiar y pegar el contenido de `surf-radar-workflow.yml.txt`, distribuido por separado junto al ZIP.
- Commit changes en la rama principal `main`.
- Si `.github/workflows/surf-radar.yml` ya existe, NO crearlo por duplicado.

## Paso 4: publicar
- Settings > Pages > Build and deployment > Source > GitHub Actions.
- Actions > Actualizar Surf Radar > Run workflow > main > Run workflow.
- Comprobar que estén verdes los pasos de tests, cálculo y publicación.
- URL orientativa: https://TU_USUARIO.github.io/barcelona-surf-radar/

## Paso 5: alertas Telegram (opcional después)
- Crear bot mediante @BotFather en Telegram y abrir un chat con /start.
- Obtener el chat ID de tu bot y guardar dos valores como repository secrets:
  `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
- Settings > Secrets and variables > Actions > New repository secret.
- Nunca añadir el token a ningún archivo del repositorio ni compartirlo por chat.
- Sin un buen pronóstico no llegará ningún aviso; eso es normal.

## Nota
- GitHub Pages publica archivos de pronóstico, pero la calidad del ranking necesita calibración.
- GitHub Actions intenta actualizar 4 veces al día; la programación puede retrasarse.
- El ZIP contiene un workflow que copia las fichas locales de surf durante el despliegue.
