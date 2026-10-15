# Barcelona Surf Radar v1.1 🏄

Web móvil y **PWA instalable** para comparar 7 playas entre **Sant Sebastià y Mar Bella** en Barcelona, encontrar la mejor franja horaria de surf y enviar **alertas por Telegram**. El workflow de GitHub Actions se ejecuta **cada 6 horas UTC** (con posibles retrasos normales del programador de GitHub).

El proyecto es funcional, pero **este paquete no está publicado ni tiene conectado un bot de Telegram**. Para recibir notificaciones hay que desplegar el repositorio y configurar dos secretos personales. `data/latest.json` está vacío deliberadamente; los resultados aparecen al ejecutar por primera vez el workflow, no son datos de ejemplo presentados como pronóstico real.

## Qué incluye

- Ranking **Top 3** entre Sant Sebastià, Sant Miquel, Barceloneta, Somorrostro, Nova Icària, Bogatell y Mar Bella.
- **Fichas individuales por playa**: swell ideal, viento favorable, mejor/peor escenario, marea, peligros, fuentes y estado de validación (documentado vs. provisional). Se pueden consultar incluso antes de activar el parte meteorológico.
- **Scoring individual real en código**: cada playa tiene su propio centro de dirección del swell y viento favorable. Se informa de si el swell y viento se alinean con la ficha. No se exagera la precisión: factores de exposición = 1 hasta calibrarlos.

- Previsión **horaria** de olas (m), período (s), swell, viento (kn), temperatura, lluvia, nivel del mar modelado, dirección, rachas, confianza y recomendación de 1–2 horas.
- Modos **iniciación, intermedio y avanzado** y vistas **hoy, mañana y pasado mañana**. Guardado de preferencia en móvil.
- Modelo comparativo de **ECMWF WAM, DWD EWAM, GFS Wave y Météo-France Wave** para oleaje; **AROME, ICON-EU y GFS** para viento. Los datos se obtienen mediante **Open-Meteo** con APIs JSON autorizadas. Si un modelo no cubre el área, no se inventan sus valores: el sistema sigue con los modelos disponibles y reduce la confianza.
- Soporte **opcional** para la API **profesional de Windy**: agrega Windy AROME y Windy GFS Wave si configurás una clave real y la variable `WINDY_PRODUCTION=1`; **no** usar API testing para producción.
- Enlaces a **Windguru, Windy, Surf-Forecast y Portus** para verificar manualmente (Windguru y Surf-Forecast **no forman parte de la comparación automática** por falta de una API pública de lectura que hayamos podido verificar).
- La app marca los partes de más de **8 horas** como antiguos y puede funcionar con caché offline señalizando la antigüedad.
- Telegram alerta cuando una **sesión de dos horas seguidas** supera **76/100**, dentro de las próximas 42 horas, si ambos instantes son diurnos, no hay riesgos calculados y se tienen **mínimo dos modelos marinos**. Evita repetir notificaciones de la misma fecha.

## Publicación sin mantener un servidor

### 1) Subirlo a GitHub

1. Creá en GitHub un repositorio **público** con nombre sugerido `barcelona-surf-radar`.
2. Subí **el contenido** del ZIP al raíz del repositorio, NO una carpeta contenedora. Deben verse `index.html`, `app.js`, `styles.css`, `data/`, `scripts/`, `tests/`, `assets/`. La automatización debe existir en `.github/workflows/surf-radar.yml`. En GitHub web, la subida de la carpeta oculta `.github` puede fallar: en ese caso, usá **Add file → Create new file**, escribí esa ruta completa y pegá el contenido del archivo YAML suministrado por separado. No subas el ZIP sin descomprimir. También podés usar GitHub Desktop o `git init`, `git add .`, `git commit` y `git push`.
3. En **Settings → Pages**, elegí **Build and deployment → Source: GitHub Actions**. No elijas «Deploy from a branch». El workflow de publicación incluye los perfiles de playas (`data/spot_profiles.json`) y los archivos gráficos.
4. En **Actions → Actualizar Surf Radar → Run workflow**, ejecutalo manualmente para la primera actualización. Después se ejecutará cada seis horas en los minutos 17 de UTC 00, 06, 12 y 18, salvo retrasos operativos de GitHub.
5. Al completarse **Pages**, abrí `https://TU_USUARIO.github.io/barcelona-surf-radar/`. Si el repo tiene otro nombre, cambiá el final de la URL. Podés compartirlo como enlace o **Añadir a pantalla de inicio** para verlo como app instalada.

> **Importante:** no puede garantizarse un refresco *exactamente* cada 6 horas con el programador de GitHub Actions, aunque sí intenta hacerlo con esa periodicidad.

### 2) Activar alertas reales en Telegram

1. En la app Telegram, abrí **@BotFather**, creá un bot con `/newbot` y guardá el token.
2. Mandale `/start` a tu bot nuevo. Averiguá tu **chat ID** con el endpoint oficial de Telegram `getUpdates` de ese bot (tu `chat.id` aparecerá después de enviarle `/start`). No publiques ni compartas el token del bot.
3. En tu repositorio de GitHub → **Settings → Secrets and variables → Actions → New repository secret**, agregá:
   - `TELEGRAM_BOT_TOKEN` = el token secreto.
   - `TELEGRAM_CHAT_ID` = tu ID numérico de chat.
4. Si la URL publicada **no** coincide con `https://TU_USUARIO.github.io/NOMBRE_REPO/`, agregá una **variable del repositorio** llamada `SITE_URL` con la URL completa de tu web. **No** uses un secreto para esta URL pública.
5. Volvé a ejecutar el workflow. Si hay una buena ventana y cumple los criterios, recibirás un mensaje al móvil con el enlace al dashboard. Si no hay buenas condiciones **no se envía nada**.

Para modificar el mínimo de calidad que desencadena avisos, agregá la **variable** `ALERT_THRESHOLD` en *Settings → Secrets and variables → Actions → Variables* (valor por defecto: `76`; permitido: entre 65 y 94). El dashboard mostrará el umbral configurado desde la siguiente actualización.

### 3) APIs profesionales opcionales

- `WINDY_API_KEY` (**secret**): habilita la API Point Forecast oficial de Windy, modelo `arome` para viento y `gfsWave` para oleaje. La clave de prueba de Windy retorna datos alterados y no se debe utilizar para mensajes reales. El servicio profesional tenía precio de **990 €/año** al preparar este proyecto; confirmar tarifa vigente antes de contratar.
- `OPEN_METEO_API_KEY` (**secret**): solo si querés una licencia comercial de Open-Meteo. Para la **versión personal, sin monetizar** no hace falta clave. Siempre acreditamos a Open-Meteo por CC BY 4.0.

**Limitación de fuentes:** Windguru y Surf-Forecast se integran como enlaces de comprobación, no como un alimentador automático de series. No se hace scraping ni se expone una clave privada en el HTML/JS.

## Ejecutar localmente

```bash
python3 -m unittest discover -s tests -v
python3 scripts/update.py
python3 -m http.server 8000
```

Abrí `http://localhost:8000` desde el navegador. Para consultar desde otro móvil en la misma red, usá la IP local de tu ordenador en lugar de `localhost`. El refresco local **no** queda programado automáticamente: utilizá el workflow incluido o un `cron` propio. Requiere conexión a internet para ejecutar `scripts/update.py`.

## Qué significa el ranking

Es una **heurística transparente por playa**, no un modelo calibrado con medidas de cada pico. Pondera aproximadamente altura (37%), período (22%), calidad y dirección del viento (17%), orientación de swell (16%) y proporción de swell (8%). La orientación óptima del swell, la tolerancia angular y la dirección del viento offshore provienen de `data/spot_profiles.json`. Penaliza divergencia de modelos, ausencia de datos, tormentas, ráfagas fuertes y mar insuficiente. Tiene tres perfiles; la alerta del servidor utiliza el perfil **intermedio** por defecto, independientemente del perfil seleccionado en el móvil.

**La altura de ola del modelo es altura significativa mar adentro, NO altura del rompiente.** Los espigones, la batimetría y bancos de arena pueden cambiar el surf en pocas decenas de metros. Las playas de Barcelona están muy juntas en comparación con la resolución de los modelos, por lo que diferencias pequeñas del ranking son aproximadas y podrían ser empates técnicos. La selección de spots es una aproximación inicial que conviene calibrar con observación local. El factor numérico de exposición se mantiene en **1.0 para las 7 playas**: no inventamos aumentos o disminuciones porcentuales de altura por estar junto a un espigón. La puntuación puede tener **empates técnicos** si los resultados difieren por 5 puntos o menos.

**La marea aún no suma ni resta puntos al ranking.** Está documentada una preferencia por bajamar en Sant Sebastià, pero falta validarla y relacionar el nivel del agua del puerto con la batimetría del pico. **El nivel del mar modelado NO equivale a horarios exactos de pleamar y bajamar.** Para las mareas oficiales consultá Puertos del Estado (Portus). La marea astronómica del Mediterráneo suele tener menor influencia que viento, oleaje y forma del fondo en estos spots. No reemplaza condiciones de seguridad, bandera de baño, prohibiciones locales, corrientes ni una inspección visual antes de entrar.

## Perfiles de los siete spots: qué sabemos y qué falta medir

Las fichas se guardan en `data/spot_profiles.json`, que consumen tanto el algoritmo Python como la interfaz web. Se pueden editar y versionar sin alterar los otros módulos. La fuente y el nivel de confianza de cada ficha quedan accesibles en la web.

| Playa | Swell óptimo inicial | Viento favorable inicial | Base de la ficha |
|---|---|---|---|
| Sant Sebastià | E | W | Surf-Forecast (documentado) |
| Sant Miquel | E–ESE | W–WNW | Hipótesis por proximidad; pendiente |
| Barceloneta | E–ESE | W–WNW | Surf-Forecast / WeWave (documentado) |
| Somorrostro | E–ESE | W–NW | BCN Surf School agrupa con Barceloneta; pendiente |
| Nova Icària | E–SE | W–NW | Hipótesis de exposición; pendiente |
| Bogatell | ESE–SE | NW | Surf-Forecast / WeWave (documentado) |
| Mar Bella | SE | NW | WeWave (documentado) |

**Mar Bella NO es Nova Mar Bella.** La ficha del breakwater de Nova Mar Bella que aparece en algunas guías corresponde a una playa diferente y no se ha utilizado para parametrizar Mar Bella.

### Cómo pasar de hipótesis a datos calibrados

1. Registrar una sesión o inspección visual por playa con fecha, sector del espigón, modelo previsto y altura de ola observada; usar `data/spot_observations_template.csv`. No cargar datos simulados.
2. Comparar el estado real y las series previstas del mismo momento. Revisar errores sistemáticos de altura, dirección, período y calidad, distinguiendo distintos sectores dentro de la misma playa.
3. Tras varias decenas de observaciones por zona y diferentes temporales, ajustar sectores angulares, preferencias de nivel del mar y exposición. **La versión 1.1 no recalibra automáticamente**: el CSV es una plantilla para una futura fase de aprendizaje.
4. Revisar perfiles tras temporales, dragados o cambios de banco de arena y registrar la versión del perfil con cada evaluación.

**Seguridad:** tormentas y rachas fuertes reducen la puntuación. Todavía no se ingieren automáticamente banderas rojas ni resultados microbiológicos en tiempo real: antes de entrar hay que consultar el estado de las playas de Protección Civil, especialmente durante temporales y después de lluvias intensas. Fuente: [Protecció Civil](https://interior.gencat.cat/es/arees_dactuacio/proteccio_civil/estatplatges/) y [Agència Catalana de l'Aigua](https://aca.gencat.cat/es/laigua/estat-del-medi-hidric/qualitat-de-les-aiguees-de-bany/index.html).

## Estructura del proyecto

```
index.html, styles.css, app.js   Interfaz estática móvil
manifest.webmanifest, sw.js     Instalable como PWA
assets/                         Iconos
scripts/forecast.py             APIs marinas y scoring
scripts/alerts.py               Ventanas de alerta, dedupe y Telegram
scripts/update.py               Actualización con escritura atómica
.github/workflows/surf-radar.yml  Cada 6 horas y GitHub Pages
state/alerts.json               Registro de días ya notificados
data/spot_profiles.json         Perfiles documentados e hipótesis por playa
 data/spot_observations_template.csv Plantilla de observaciones reales
 data/latest.json               Archivo generado con series JSON
 tests/                         Tests sin conexión a internet
```

## Fuentes y licencias consultadas

- [Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api)
- [Open-Meteo Météo-France AROME](https://open-meteo.com/en/docs/meteofrance-api)
- [Open-Meteo Terms / licencia](https://open-meteo.com/en/terms)
- [Windy Point Forecast API](https://api.windy.com/point-forecast/docs) y [tarifas](https://api.windy.com/point-forecast/pricing)
- [Windguru Barceloneta](https://www.windguru.cz/501033)
- [Surf-Forecast Sant Sebastià](https://www.surf-forecast.com/breaks/Playade-Sant-Sebastia), [Barceloneta](https://www.surf-forecast.com/breaks/Barceloneta) y [Bogatell](https://www.surf-forecast.com/breaks/Bogatell)
- [WeWave Mar Bella](https://wewave.surf/es/spots/mar-bella)
- [BCN Surf School, guía local de spots](https://bcnsurfschool.es/es/mar/donde-surfear-en-barcelona)
- [Puertos del Estado: cómo interpretar olas medidas en mar abierto](https://www.puertos.es/servicios/oceanografia/faqs)
- [Puertos del Estado, nivel del mar](https://www.puertos.es/servicios/oceanografia/faqs)

**Aviso:** predicciones aproximadas; utilizar a criterio propio y verificar los avisos de Protección Civil de Cataluña y salvamento marítimo. Sin garantía de condiciones de surf ni de seguridad en el agua.
