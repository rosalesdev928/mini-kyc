## ¿Qué es el proceso de onboarding digital?
El onboarding digital te permite abrir tu cuenta en línea. Ingresas tu correo, subes una foto de tu documento de identidad y leemos los datos automáticamente. No necesitas ir a una agencia ni hacer trámites en papel. También se conoce como KYC (Know Your Customer) o registro de clientes.

## ¿Qué documentos puedo usar?
Puedes subir un DNI peruano (documento nacional de identidad), un carné de extranjería o un pasaporte. El documento debe estar vigente, ser original y no estar vencido. No se aceptan fotocopias ni capturas de otras pantallas.

## ¿Qué formatos y tamaños de imagen se aceptan?
Solo se aceptan imágenes JPG y PNG, de hasta 5 MB cada una. La imagen debe tener al menos 300 píxeles en su lado más corto. Los archivos PDF y otros formatos se rechazan con un mensaje de tipo de archivo no admitido.

## ¿Cómo tomo una buena foto de mi documento?
Coloca el documento sobre una superficie plana y oscura, con buena luz natural. Evita reflejos, sombras y bordes cortados. Mantén la cámara quieta para que todo el documento salga nítido y todo el texto se pueda leer. Las fotos borrosas se rechazan y puedes volver a tomarlas sin problema.

## ¿Por qué mi imagen fue rechazada por borrosa?
El sistema mide la nitidez de la imagen antes de leerla. Si el texto está desenfocado, muy oscuro o movido, la imagen se rechaza como borrosa. Vuelve a tomar la foto con pulso firme, más luz y sin reflejos, y súbela otra vez.

## ¿Qué datos se extraen de mi documento?
Extraemos tu nombre completo, tu número de documento y el tipo de documento. También registramos qué tan segura es la lectura, que se muestra como el porcentaje de confianza OCR. Tu correo y los datos extraídos se guardan junto con la fecha y la hora del registro.

## ¿Qué significa la confianza OCR?
Es un porcentaje que indica qué tan segura está la inteligencia artificial de haber leído bien tu nombre y tu número de documento. Los registros con confianza alta se marcan como Verificado. Los de confianza más baja se marcan como Por revisar y un operador los revisa manualmente.

## ¿Qué significa el estado Por revisar?
Significa que la lectura automática no tuvo suficiente confianza, o que el número de documento no coincidía con el formato esperado. No es un rechazo. Un operador del banco revisará el registro manualmente y puede contactarte por correo.

## ¿Guardan mi foto del documento?
No. La foto se envía al servicio de inteligencia artificial solo para leer el texto y no se guarda en nuestra base de datos. Guardamos tu correo, tu nombre, tu número de documento, la confianza y una huella técnica (hash) de la imagen, junto con la fecha y la hora.

## ¿Mi información está segura?
Los secretos, como las claves de API, se guardan en variables de entorno y nunca en el código fuente. La imagen se valida antes de procesarla y la conexión con el servicio debe usar HTTPS. Solo se guarda el mínimo de datos necesario para el registro.

## ¿Cuánto demora el proceso?
Leer un documento normalmente toma unos segundos. La página muestra un estado de carga mientras se procesa el documento. Si el servicio de IA está ocupado, es posible que te pida intentarlo de nuevo en un minuto.

## ¿Qué pasa si el sistema no pudo leer mi nombre o mi número?
Vuelve a tomar la foto de modo que se vea todo el documento, sin reflejos y sin bordes cortados, y súbela otra vez. Si el problema continúa, contacta con atención al cliente y un operador puede completar el registro manualmente.

## ¿Puedo registrarme más de una vez con el mismo correo?
Sí. Cada carga crea un nuevo registro de onboarding vinculado al mismo correo, así que puedes reintentar después de un intento fallido o de baja confianza.

## ¿Se pueden borrar mis datos personales?
Sí. Los registros se anonimizan automáticamente después de un periodo de retención (30 días por defecto) y un operador puede borrar los datos personales de un registro si lo pides. El nombre, el número de documento y el nombre del archivo se reemplazan por marcadores y se desvincula el correo; solo se conserva un historial técnico de auditoría.
