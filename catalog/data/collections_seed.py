"""
Colecciones iniciales de Pegasus Store México (noviembre 2026), elegidas por
los tipos de producto con más referencias en el catálogo de Dropi México.
Cada texto está escrito para su tipo de producto, con vocabulario mexicano
(bocina, refrigerador, auto, lentes) y sin plantillas: Google trata el texto
repetido con plantilla como contenido hecho en masa. Los suplementos no
prometen efectos en la salud (COFEPRIS).

`manage.py refresh_collections --load-seed` las crea si no existen (no pisa
lo editado en el admin, salvo con --overwrite-seed) y publica solo las que
tienen al menos MIN_PRODUCTS_TO_PUBLISH productos.

Campos: category (clave de la categoría de la tienda), slug, name, include,
exclude, intro (párrafos separados por línea en blanco), faq [(pregunta,
respuesta)].
"""

SEED = [
    # ── tecnologia ────────────────────────────────────────────────────────────
    {
        "category": 'tecnologia', "slug": 'bocinas-bluetooth', "name": 'Bocinas bluetooth',
        "include": ['bocina', 'bafle', 'parlante', 'altavoz'],
        "exclude": ['auto', 'carro', 'coche'],
        "intro": (
            'Bocinas portátiles para la fiesta, la cochera, la playa o el cuarto: desde mini bocinas que caben en la mano hasta bafles con luces, micrófono para karaoke y batería para toda la tarde. Casi todas se conectan por bluetooth al celular y muchas también leen USB, memoria micro SD o radio FM.\n\n'
            'Para escoger, fíjate en tres datos de la ficha: la potencia en watts (más watts, más volumen), las horas de batería y si es resistente al agua. Si la quieres para karaoke, busca las que traen micrófono incluido o entrada para conectarlo.'
        ),
        "faq": [
            ('¿Qué bocina me conviene para fiestas?',
             'Una de 20 W o más, con batería de varias horas y, si se puede, con luces y entrada para micrófono. Para el cuarto o la oficina basta una mini bocina de 5 a 10 W.'),
            ('¿Las bocinas bluetooth funcionan con cualquier celular?',
             'Sí, se enlazan con cualquier celular Android o iPhone con bluetooth. Muchas también reproducen música desde USB o memoria micro SD sin celular.'),
        ],
    },
    {
        "category": 'tecnologia', "slug": 'barras-de-sonido', "name": 'Barras de sonido',
        "include": ['barra de sonido', 'barra sonido', 'soundbar'],
        "exclude": [],
        "intro": (
            'Una barra de sonido debajo de la pantalla cambia por completo las películas, el futbol y los videojuegos: los diálogos se escuchan claros sin subirle tanto al volumen. Aquí hay barras para pantalla y también portátiles con batería y bluetooth.\n\n'
            'Revisa en la ficha cómo se conecta: bluetooth, cable auxiliar, óptico o HDMI. Si tu pantalla es reciente casi siempre tiene bluetooth u óptico; si es antigua, la entrada auxiliar de 3.5 mm es la más segura.'
        ),
        "faq": [
            ('¿Cómo conecto la barra de sonido a mi pantalla?',
             'Por bluetooth si tu pantalla lo tiene, o por cable auxiliar, óptico o HDMI según el modelo. En cada ficha aparecen las conexiones de la barra.'),
            ('¿Sirve para algo más que la tele?',
             'Sí, las que tienen bluetooth también reproducen música desde el celular o la computadora.'),
        ],
    },
    {
        "category": 'tecnologia', "slug": 'audifonos-inalambricos', "name": 'Audífonos inalámbricos',
        "include": ['audifonos', 'audifono', 'auriculares', 'auricular', 'diadema bluetooth', 'manos libres'],
        "exclude": ['lentes'],
        "intro": (
            'Audífonos bluetooth para el trabajo, el gimnasio y el transporte: in-ear tipo TWS con estuche de carga, de diadema con mejor aislamiento, deportivos que no se caen y modelos con pantalla táctil en el estuche.\n\n'
            'Compara la versión de bluetooth (5.0 o mayor se conecta más estable), la duración de batería con el estuche y si tienen micrófono para llamadas. Para hacer ejercicio busca los que dicen resistentes al sudor.'
        ),
        "faq": [
            ('¿Funcionan con iPhone y con Android?',
             'Sí, los audífonos bluetooth se enlazan con cualquier celular. Algunas funciones táctiles pueden variar según el teléfono.'),
            ('¿Cuánto dura la batería?',
             'Depende del modelo; en la ficha verás las horas de uso continuo y cuántas cargas adicionales da el estuche.'),
        ],
    },
    {
        "category": 'tecnologia', "slug": 'relojes-inteligentes', "name": 'Relojes inteligentes',
        "include": ['smartwatch', 'reloj inteligente', 'smart watch', 'smartband', 'banda inteligente', 'reloj smart'],
        "exclude": [],
        "intro": (
            'Smartwatches y bandas inteligentes que te avisan de llamadas y mensajes, cuentan pasos, miden ritmo cardiaco y registran tu sueño. Hay modelos de pantalla grande tipo Ultra, redondos más discretos y bandas ligeras para hacer ejercicio.\n\n'
            'Antes de pedir revisa que la app del reloj sea compatible con tu celular (casi todos funcionan con Android y iPhone) y cuántos días dura la batería. Las mediciones de salud son orientativas, no sustituyen un aparato médico.'
        ),
        "faq": [
            ('¿Puedo contestar llamadas desde el reloj?',
             'Solo en los modelos que indican llamadas bluetooth con micrófono y bocina. Los demás te notifican la llamada para que la contestes en el celular.'),
            ('¿Se puede meter al agua?',
             'Depende de la certificación que aparece en la ficha: IP67 aguanta salpicaduras y lluvia; IP68 permite lavarse las manos o nadar en superficie.'),
        ],
    },
    {
        "category": 'tecnologia', "slug": 'cargadores-y-power-banks', "name": 'Cargadores y power banks',
        "include": ['cargador', 'power bank', 'powerbank', 'bateria portatil', 'bateria externa', 'cargador inalambrico'],
        "exclude": ['bateria de auto', 'cargador de bateria', 'pilas', 'audifonos', 'aromatizante', 'techo'],
        "intro": (
            'Power banks para no quedarte sin pila fuera de casa, cargadores rápidos USB-C, bases de carga inalámbrica y estaciones 3 en 1 para cargar celular, reloj y audífonos al mismo tiempo.\n\n'
            'En los power banks fíjate en los mAh: 10,000 mAh cargan un celular unas dos veces y 20,000 mAh unas cuatro. En cargadores, los watts marcan la velocidad: 20 W o más ya es carga rápida para la mayoría de los teléfonos.'
        ),
        "faq": [
            ('¿Puedo subir un power bank al avión?',
             'Las aerolíneas suelen permitir power banks de hasta 20,000 mAh en el equipaje de mano, nunca en la maleta documentada. Confírmalo con tu aerolínea.'),
            ('¿La carga inalámbrica funciona con mi celular?',
             'Funciona con celulares que tienen carga Qi, como los iPhone desde el 8 y muchos Android de gama media y alta. Revisa la ficha técnica de tu teléfono.'),
        ],
    },
    {
        "category": 'tecnologia', "slug": 'cables-y-adaptadores', "name": 'Cables y adaptadores',
        "include": ['cable', 'adaptador', 'convertidor', 'hub', 'cable hdmi', 'cable usb'],
        "exclude": ['organizador', 'pasa cable', 'cinta'],
        "intro": (
            'Cables HDMI para conectar la laptop o la consola a la pantalla, cables USB-C y Lightning de carga rápida, cables de red y adaptadores para lo que tu equipo no trae: USB a Ethernet, HDMI a VGA, hubs con varios puertos.\n\n'
            'Mide la distancia antes de pedir: un cable HDMI muy corto no llega y uno muy largo estorba. Para pantallas 4K busca cables HDMI 2.0 o superior.'
        ),
        "faq": [
            ('¿Qué cable HDMI necesito para 4K?',
             'Uno HDMI 2.0 o 2.1. Los de nylon trenzado aguantan mejor que se doblen.'),
            ('¿Cómo sé qué adaptador necesita mi laptop?',
             'Revisa qué puertos tiene (USB-C, USB-A, HDMI) y qué quieres conectar. En cada ficha dice de qué conector a qué conector va el adaptador.'),
        ],
    },
    {
        "category": 'tecnologia', "slug": 'soportes-para-celular', "name": 'Soportes para celular',
        "include": ['soporte para celular', 'soporte celular', 'soporte de celular', 'holder', 'tripie', 'tripode', 'soporte magnetico'],
        "exclude": [],
        "intro": (
            'Soportes para usar el celular en el auto como navegador, en el escritorio para videollamadas o en la cocina para seguir una receta, además de tripiés y bastones para selfies y videos.\n\n'
            'Para el auto hay de rejilla, de ventosa y magnéticos; revisa si el tuyo necesita placa metálica o si sujeta con pinzas. Para grabar, un tripié con control bluetooth te deja tomar la foto a distancia.'
        ),
        "faq": [
            ('¿Los soportes magnéticos dañan el celular?',
             'No, el imán no afecta el teléfono. Solo necesitas pegar la placa metálica que viene incluida en la funda o en el celular.'),
            ('¿Sirven para tablet?',
             'Algunos sí; la ficha indica el tamaño máximo de pantalla que sostiene.'),
        ],
    },
    {
        "category": 'tecnologia', "slug": 'aros-de-luz-y-microfonos', "name": 'Aros de luz y micrófonos',
        "include": ['aro de luz', 'aro luz', 'microfono', 'microfonos', 'lavalier'],
        "exclude": ['bocina'],
        "intro": (
            'Lo necesario para grabar videos, hacer transmisiones en vivo o cantar karaoke: aros de luz con tripié, micrófonos inalámbricos de solapa para el celular y micrófonos de karaoke con bocina.\n\n'
            'Un aro de luz de 10 pulgadas alcanza para maquillaje y videos de cerca; para tomas de cuerpo completo conviene uno más grande. En micrófonos de solapa revisa si conectan por USB-C o Lightning según tu teléfono.'
        ),
        "faq": [
            ('¿El micrófono inalámbrico funciona con mi celular?',
             'Sí, si coincide el conector: USB-C para la mayoría de Android y iPhone recientes, Lightning para iPhone anteriores al 15.'),
            ('¿El aro de luz trae tripié?',
             'La mayoría sí; la ficha indica la altura máxima y si incluye soporte para el celular.'),
        ],
    },
    # ── seguridad ─────────────────────────────────────────────────────────────
    {
        "category": 'seguridad', "slug": 'camaras-de-seguridad', "name": 'Cámaras de seguridad',
        "include": ['camara de seguridad', 'camara wifi', 'camara ip', 'mini camara', 'camara espia', 'camara foco', 'camara bombillo', 'camara solar', 'camara exterior', 'camara 360', 'camara bateria'],
        "exclude": ['auto', 'reversa', 'tablero'],
        "intro": (
            'Cámaras WiFi para vigilar la casa, el negocio o al bebé desde el celular: mini cámaras discretas, cámaras tipo foco que se enroscan en un socket, cámaras exteriores con panel solar y modelos con giro de 360°.\n\n'
            'Revisa si guardan el video en memoria micro SD o en la nube, si tienen visión nocturna y si te avisan al detectar movimiento. Todas necesitan señal WiFi donde las vas a instalar.'
        ),
        "faq": [
            ('¿Necesito internet para usar la cámara?',
             'Para verla desde el celular sí, necesita WiFi. Algunas siguen grabando en la memoria micro SD aunque se vaya el internet.'),
            ('¿Las cámaras tipo foco son fáciles de instalar?',
             'Sí, se enroscan en un socket normal de foco E27 y se configuran desde la app; no hace falta cablear.'),
        ],
    },
    # ── hogar ─────────────────────────────────────────────────────────────────
    {
        "category": 'hogar', "slug": 'focos-y-reflectores', "name": 'Focos y reflectores LED',
        "include": ['foco', 'focos', 'reflector', 'reflectores', 'lampara de techo', 'plafon'],
        "exclude": ['camara', 'ventilador'],
        "intro": (
            'Focos LED para la casa, reflectores para el patio o la cochera, plafones y lámparas de techo que gastan mucho menos luz que los focos de antes. También hay focos de emergencia que siguen prendidos cuando se va la luz.\n\n'
            'Fíjate en los watts (consumo) y el tono: luz blanca fría para cocina, cochera y trabajo; luz cálida para recámaras y sala. Revisa también el tipo de rosca, que en México casi siempre es E27.'
        ),
        "faq": [
            ('¿Qué foco reemplaza a uno de 100 W de los antiguos?',
             'Uno LED de unos 12 a 15 W da una luz parecida y consume mucho menos.'),
            ('¿Los reflectores se pueden poner a la intemperie?',
             'Sí, los que dicen IP65 o IP66 aguantan lluvia y polvo. Revisa la certificación en la ficha.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'ventiladores', "name": 'Ventiladores',
        "include": ['ventilador', 'ventiladores', 'aire acondicionado', 'enfriador', 'abanico'],
        "exclude": ['cama', 'pelo'],
        "intro": (
            'Ventiladores para el calor de todo el país: de techo con lámpara, de pie, de mesa, de torre, recargables de cuello y de mano, para el auto, y enfriadores de aire que refrescan con agua o hielo.\n\n'
            'Para un cuarto completo conviene uno de techo o de pie; para la oficina o el transporte, uno recargable portátil. Los enfriadores evaporativos funcionan mejor en clima seco que en clima húmedo de costa.'
        ),
        "faq": [
            ('¿Un enfriador de aire es lo mismo que un minisplit?',
             'No. El enfriador refresca con agua o hielo y es portátil; baja algunos grados el aire cercano, sobre todo en clima seco. No sustituye un aire acondicionado.'),
            ('¿Cuánto dura la batería de un ventilador recargable?',
             'Varía según el modelo y la velocidad; en la ficha aparecen las horas aproximadas.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'lamparas-solares', "name": 'Lámparas solares',
        "include": ['lampara solar', 'luz solar', 'reflector solar', 'farol solar', 'luces solares'],
        "exclude": [],
        "intro": (
            'Lámparas que se cargan con el sol y prenden solas al anochecer: para la entrada, el jardín, la barda, la cochera o el patio, sin cables y sin subir el recibo de luz. Muchas traen sensor de movimiento.\n\n'
            'Ponlas donde les dé el sol directo varias horas al día. Revisa en la ficha si el panel viene integrado o separado con cable (útil cuando la lámpara queda bajo techo).'
        ),
        "faq": [
            ('¿Funcionan en días nublados?',
             'Cargan menos, así que duran menos horas en la noche. Con sol directo recuperan la carga completa.'),
            ('¿Necesitan instalación eléctrica?',
             'No, solo se atornillan o se clavan en el lugar donde les dé el sol.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'lamparas-led-y-decorativas', "name": 'Lámparas LED',
        "include": ['lampara led', 'lampara de mesa', 'lampara decorativa', 'lampara de escritorio', 'lampara nocturna', 'luz nocturna', 'lampara de luna', 'lampara de noche'],
        "exclude": ['ventilador', 'techo', 'integrada', 't8'],
        "intro": (
            'Lámparas LED recargables para cuando se va la luz, lámparas de escritorio para estudiar, luces nocturnas y lámparas para salas y recámaras con varios tonos de luz.\n\n'
            'Si buscas una lámpara para apagones, elige una recargable con varias horas de batería. Para leer o trabajar, una con brazo ajustable y luz blanca neutra cansa menos la vista.'
        ),
        "faq": [
            ('¿Cuánto dura una lámpara recargable?',
             'Depende de la batería y la intensidad; en la ficha encontrarás las horas aproximadas de uso.'),
            ('¿Qué tono de luz es mejor para estudiar?',
             'La luz blanca neutra o fría ayuda a concentrarse; la cálida es mejor para relajarse antes de dormir.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'tiras-y-luces-led', "name": 'Tiras y luces LED',
        "include": ['tira led', 'tiras led', 'cinta led', 'luces led', 'manguera led', 'luces navidenas', 'serie de luces'],
        "exclude": [],
        "intro": (
            'Tiras LED para decorar la recámara, el escritorio gamer o detrás de la pantalla, mangueras LED para exteriores y series de luces para Navidad, posadas y fiestas.\n\n'
            'Mide el largo que necesitas antes de pedir y revisa si la tira se controla con app, con control remoto o con ambos. Para exteriores busca las que indican uso exterior o resistencia al agua.'
        ),
        "faq": [
            ('¿Las tiras LED se pueden cortar?',
             'Muchas sí, en las marcas indicadas sobre la tira. La ficha aclara si el modelo lo permite.'),
            ('¿Se pegan solas?',
             'La mayoría trae cinta adhesiva por detrás. Limpia bien la superficie para que se sostengan mejor.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'aspiradoras', "name": 'Aspiradoras',
        "include": ['aspiradora', 'aspiradoras'],
        "exclude": [],
        "intro": (
            'Aspiradoras portátiles de mano, aspiradoras para el auto, verticales 2 en 1 y robots que barren y trapean solos. Útiles para pelo de mascota, migajas, polvo y los asientos del coche.\n\n'
            'Compara la potencia de succión, si es inalámbrica o de cable y la capacidad del depósito. Para el auto, las de 12 V se conectan al encendedor; las recargables son más prácticas para la casa.'
        ),
        "faq": [
            ('¿Sirven para pelo de mascota?',
             'Sí, sobre todo las que traen cepillo o boquilla para tapicería. Revisa los accesorios incluidos en la ficha.'),
            ('¿Las aspiradoras para auto se conectan al encendedor?',
             'Algunas sí, a 12 V; otras son recargables por USB. La ficha indica cuál es.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'regaderas-y-bano', "name": 'Regaderas y accesorios de baño',
        "include": ['regadera', 'ducha', 'grifo', 'llave mezcladora', 'organizador de bano', 'dispensador de jabon', 'cortina de bano'],
        "exclude": ['fregadero', 'cocina'],
        "intro": (
            'Regaderas de alta presión con filtro, mangueras, grifos giratorios, organizadores de esquina, dispensadores de jabón y accesorios para que el baño quede más práctico y ordenado.\n\n'
            'Antes de cambiar la regadera revisa que la rosca sea estándar de 1/2 pulgada, la más común en México. Para organizadores sin taladrar, busca los de adhesivo o los ajustables a presión.'
        ),
        "faq": [
            ('¿La regadera con filtro mejora la presión?',
             'Las regaderas de alta presión concentran el agua en orificios más pequeños y se sienten con más fuerza, aunque la presión real depende de tu instalación.'),
            ('¿Los organizadores necesitan taladro?',
             'Hay modelos adhesivos y ajustables que no necesitan taladrar; la ficha indica cómo se instala cada uno.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'organizadores-de-ropa-y-closet', "name": 'Clósets y organizadores de ropa',
        "include": ['closet', 'armario', 'organizador de ropa', 'ropero', 'perchero', 'ganchos para ropa', 'organizador closet'],
        "exclude": [],
        "intro": (
            'Clósets armables, roperos plegables, percheros y organizadores para aprovechar el espacio cuando el cuarto no tiene clóset o ya no alcanza.\n\n'
            'Mide el alto, ancho y fondo del lugar antes de pedir. Los clósets de tela con estructura metálica se arman sin herramienta y se pueden mover cuando cambias de casa.'
        ),
        "faq": [
            ('¿Es difícil armar un clóset desarmable?',
             'No, se arman encajando tubos y conectores, sin herramientas. Las medidas finales aparecen en la ficha.'),
            ('¿Cuánto peso aguantan?',
             'Depende del modelo; la ficha indica la carga recomendada por tubo o repisa.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'zapateros', "name": 'Zapateros',
        "include": ['zapatero', 'zapateras', 'organizador de zapatos'],
        "exclude": [],
        "intro": (
            'Zapateros de varios niveles, zapateras colgantes para la puerta y organizadores plegables para que los zapatos dejen de estar regados en la entrada o el clóset.\n\n'
            'Cuenta cuántos pares quieres guardar y mide el espacio disponible. Los colgantes de puerta aprovechan un lugar que casi nunca se usa.'
        ),
        "faq": [
            ('¿Cuántos pares caben?',
             'Cada ficha indica los niveles y el número aproximado de pares según el tamaño del calzado.'),
            ('¿Sirven para botas?',
             'Algunos modelos tienen niveles más altos o ajustables; revisa la altura entre niveles en la ficha.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'almohadas-y-cojines', "name": 'Almohadas y cojines',
        "include": ['almohada', 'cojin', 'cojines'],
        "exclude": ['altavoz', 'bocina', 'exfoliacion'],
        "intro": (
            'Almohadas ortopédicas para el cuello, cojines para la silla de la oficina o el auto, almohadas para las rodillas y cojines de gel que reparten el peso cuando pasas muchas horas sentado.\n\n'
            'Si duermes de lado, una almohada entre las rodillas ayuda a alinear la cadera. Para trabajo de escritorio, un cojín de gel o viscoelástico hace más cómoda la jornada.'
        ),
        "faq": [
            ('¿Los cojines de gel se calientan?',
             'Están hechos para mantenerse frescos y repartir el peso mejor que un cojín de espuma normal.'),
            ('¿Se pueden lavar?',
             'La mayoría tiene funda removible y lavable; la ficha indica los cuidados.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'calentadores-y-calefactores', "name": 'Calentadores y calefactores',
        "include": ['calentador', 'calefactor', 'estufa electrica'],
        "exclude": ['agua', 'pies', 'biberon', 'biberones', 'manos', 'cera', 'taza'],
        "intro": (
            'Calefactores eléctricos para las noches frías y calentadores de paso para tener agua caliente al momento. Hay calefactores 2 en 1 que en verano funcionan como ventilador.\n\n'
            'Para un calefactor, revisa los watts y si tiene apagado automático por seguridad. En calentadores de paso, la capacidad en litros por minuto indica cuántas regaderas o tarjas abastece a la vez.'
        ),
        "faq": [
            ('¿Un calefactor eléctrico gasta mucha luz?',
             'Consume según sus watts; úsalo en espacios cerrados y por ratos para que el gasto sea menor.'),
            ('¿El calentador de paso es de gas?',
             'Revisa la ficha: indica si es de gas LP, natural o eléctrico, y la capacidad en litros.'),
        ],
    },
    {
        "category": 'hogar', "slug": 'limpieza-del-hogar', "name": 'Limpieza del hogar',
        "include": ['mop', 'trapeador', 'escoba', 'limpiador a vapor', 'destapa', 'destapa canos', 'limpiador de vidrios', 'limpiador multiusos', 'cepillo electrico de limpieza', 'cepillo de limpieza', 'cepillo giratorio', 'limpiador de ventanas', 'escobilla', 'recogedor'],
        "exclude": ['organizador', 'brochas', 'cadena', 'cadenas', 'bicicleta', 'facial', 'oidos', 'dientes', 'dental'],
        "intro": (
            'Trapeadores giratorios con cubeta, cepillos eléctricos para el baño y la cocina, limpiadores a vapor y destapacaños para que el aseo de la casa sea más rápido.\n\n'
            'Un cepillo eléctrico con varias cabezas sirve para azulejos, juntas y la estufa. El limpiador a vapor desengrasa sin químicos fuertes.'
        ),
        "faq": [
            ('¿El trapeador giratorio trae repuestos?',
             'Muchos incluyen una o dos mechas extra; la ficha dice qué viene en la caja.'),
            ('¿El limpiador a vapor sirve para cualquier piso?',
             'Funciona en loseta, cerámica y azulejo. En madera o laminado úsalo con cuidado y revisa las indicaciones.'),
        ],
    },
    # ── cocina ────────────────────────────────────────────────────────────────
    {
        "category": 'cocina', "slug": 'sartenes-y-ollas', "name": 'Sartenes y ollas',
        "include": ['sarten', 'olla', 'ollas', 'bateria de cocina', 'cacerola', 'vaporera'],
        "exclude": ['arrocera', 'pasta', 'protector', 'airfryer', 'silicona', 'limpiadora'],
        "intro": (
            'Baterías de cocina completas, sartenes antiadherentes, ollas eléctricas multifunción y vaporeras para cocinar más fácil y con menos aceite.\n\n'
            'Revisa el material del recubrimiento y si sirve para tu estufa: gas, eléctrica o inducción. Para cuidar el antiadherente, usa utensilios de madera o silicón.'
        ),
        "faq": [
            ('¿Sirven para estufa de inducción?',
             'Solo las que lo indican en la ficha; tienen fondo magnético.'),
            ('¿Cómo cuido el antiadherente?',
             'Usa utensilios de madera o silicón, lávalo con esponja suave y evita calentarlo vacío a fuego alto.'),
        ],
    },
    {
        "category": 'cocina', "slug": 'licuadoras-y-extractores', "name": 'Licuadoras y extractores',
        "include": ['licuadora', 'extractor de jugo', 'exprimidor', 'batidora'],
        "exclude": [],
        "intro": (
            'Licuadoras de vaso para la casa, licuadoras portátiles recargables para llevar el licuado al trabajo o al gym, batidoras de mano y exprimidores de cítricos.\n\n'
            'Para picar hielo o hacer salsas, busca potencia alta y cuchillas de acero inoxidable. Las portátiles son prácticas para batidos y frutas suaves.'
        ),
        "faq": [
            ('¿La licuadora portátil pica hielo?',
             'Las portátiles están pensadas para fruta y batidos; para hielo es mejor una licuadora de vaso de mayor potencia.'),
            ('¿Se puede lavar el vaso en lavavajillas?',
             'Depende del modelo; la ficha indica si el vaso es apto o si conviene lavarlo a mano.'),
        ],
    },
    {
        "category": 'cocina', "slug": 'parrillas-y-asadores', "name": 'Parrillas, asadores y planchas',
        "include": ['parrilla', 'asador', 'plancha electrica', 'sandwichera', 'waflera'],
        "exclude": ['cabello', 'pelo'],
        "intro": (
            'Asadores plegables para la carne asada del fin de semana, parrillas eléctricas, planchas para sándwiches y wafleras para desayunos rápidos.\n\n'
            'Para exteriores, un asador de carbón plegable es fácil de llevar. Para departamentos sin patio, una parrilla o plancha eléctrica no hace humo de carbón.'
        ),
        "faq": [
            ('¿La parrilla eléctrica sirve en interiores?',
             'Sí, no usa carbón ni gas. Úsala con buena ventilación por el humo de la comida.'),
            ('¿Los asadores plegables son estables?',
             'Sí, y la ficha indica las medidas de la rejilla y el material para que calcules cuánta carne cabe.'),
        ],
    },
    {
        "category": 'cocina', "slug": 'cuchillos-y-afiladores', "name": 'Cuchillos y afiladores',
        "include": ['cuchillo', 'cuchillos', 'afilador', 'afiladores'],
        "exclude": [],
        "intro": (
            'Sets de cuchillos de acero inoxidable, cuchillos de chef y afiladores para que vuelvan a cortar como nuevos.\n\n'
            'Un buen set incluye cuchillo de chef, de pan, de verduras y uno pequeño para pelar. Afílalos seguido: un cuchillo sin filo resbala y es más peligroso.'
        ),
        "faq": [
            ('¿Cada cuánto debo afilar los cuchillos?',
             'Con uso diario, una pasada por el afilador cada una o dos semanas mantiene el filo.'),
            ('¿Se pueden lavar en lavavajillas?',
             'Es mejor lavarlos a mano y secarlos de inmediato para que duren más.'),
        ],
    },
    {
        "category": 'cocina', "slug": 'picadores-y-ralladores', "name": 'Picadores y ralladores',
        "include": ['picador', 'picadora', 'rallador', 'mandolina', 'cortador de verduras', 'rebanador', 'cortador'],
        "exclude": ['pelo', 'cabello', 'unas', 'cesped', 'sierra', 'madera', 'taladro', 'vello', 'nariz', 'amoladora', 'esmeril', 'inglete', 'tela'],
        "intro": (
            'Picadoras eléctricas y manuales, ralladores giratorios, mandolinas y cortadores para picar cebolla, jitomate, chile y verduras en segundos.\n\n'
            'Para salsas y pico de gallo, una picadora de cuerda o eléctrica ahorra mucho tiempo. Las mandolinas cortan rebanadas parejas; usa siempre el protector de mano.'
        ),
        "faq": [
            ('¿Las picadoras eléctricas pican carne?',
             'Muchas sí, carne cocida o cruda en trozos pequeños. La ficha indica la potencia y la capacidad del vaso.'),
            ('¿Las cuchillas son de acero inoxidable?',
             'Sí en la mayoría; revisa la ficha de cada producto.'),
        ],
    },
    {
        "category": 'cocina', "slug": 'loncheras-electricas', "name": 'Loncheras eléctricas',
        "include": ['lonchera', 'loncheras'],
        "exclude": [],
        "intro": (
            'Loncheras que calientan la comida en el trabajo o en el auto, sin microondas. También hay loncheras térmicas de varios niveles que mantienen la temperatura.\n\n'
            'Revisa si se conecta a 110 V (enchufe de pared), a 12 V del auto o a ambos, y cuántos contenedores incluye.'
        ),
        "faq": [
            ('¿Cuánto tarda en calentar?',
             'Generalmente entre 20 y 40 minutos según la comida; la ficha indica el tiempo aproximado.'),
            ('¿Se puede usar en el auto?',
             'Solo los modelos con cable de 12 V para el encendedor; la ficha lo especifica.'),
        ],
    },
    {
        "category": 'cocina', "slug": 'termos-y-botellas', "name": 'Termos y botellas',
        "include": ['termo', 'termos', 'botella', 'vaso termico', 'vaso', 'cilindro', 'tumbler'],
        "exclude": ['dropi cup', 'lonchera', 'licuadora', 'agenda', 'boligrafo', 'cepillo', 'pastillero'],
        "intro": (
            'Termos de acero inoxidable que mantienen el café caliente o el agua fría por horas, vasos térmicos con popote, botellas para el gym y la escuela.\n\n'
            'Fíjate en la capacidad (onzas o mililitros) y si la tapa es hermética para llevarlo en la mochila. Los de doble pared de acero conservan mejor la temperatura.'
        ),
        "faq": [
            ('¿Cuánto tiempo mantiene la temperatura?',
             'Depende del termo; los de doble pared al vacío suelen mantener frío o caliente por varias horas. La ficha lo indica.'),
            ('¿Se puede meter al lavavajillas?',
             'Muchos se recomiendan lavar a mano para cuidar la pintura y el sello de la tapa.'),
        ],
    },
    {
        "category": 'cocina', "slug": 'escurridores-y-organizadores-de-cocina', "name": 'Escurridores y organizadores de cocina',
        "include": ['organizador de cocina', 'organizador cocina', 'especiero', 'escurridor', 'escurridor de platos', 'escurridor de trastes', 'organizador refrigerador', 'organizador de refrigerador', 'porta especias', 'dispensador de cereal', 'organizador de especias', 'porta cubiertos', 'organizador de alacena', 'porta rollos', 'tapete escurridor', 'organizador de fregadero', 'organizador de grifo'],
        "exclude": ['espatula'],
        "intro": (
            'Escurridores de trastes de uno y dos niveles, organizadores para el fregadero y la alacena, y accesorios para que la cocina se vea ordenada aunque sea pequeña.\n\n'
            'Mide el espacio junto al fregadero antes de elegir el escurridor. Los de acero inoxidable o cromado aguantan mejor la humedad.'
        ),
        "faq": [
            ('¿El escurridor trae charola para el agua?',
             'La mayoría sí; la ficha indica si incluye charola y portacubiertos.'),
            ('¿Se oxidan?',
             'Los de acero inoxidable o con recubrimiento cromado resisten la humedad del día a día.'),
        ],
    },
    # ── belleza ───────────────────────────────────────────────────────────────
    {
        "category": 'belleza', "slug": 'cepillos-alisadores-y-secadores', "name": 'Cepillos alisadores y secadores',
        "include": ['cepillo alisador', 'cepillo secador', 'secadora de cabello', 'secadora de pelo', 'cepillo electrico alisador', 'cepillo de aire'],
        "exclude": [],
        "intro": (
            'Cepillos de aire que secan y dan volumen en un solo paso, cepillos alisadores eléctricos y secadoras de cabello para peinarte en casa en menos tiempo.\n\n'
            'Para cabello grueso o largo, busca más potencia y varias temperaturas. Usa protector térmico antes de aplicar calor.'
        ),
        "faq": [
            ('¿El cepillo secador sustituye a la secadora?',
             'Para la mayoría de los peinados sí: seca y moldea al mismo tiempo. Si tu cabello está muy mojado, sécalo un poco con toalla antes.'),
            ('¿Sirve para cabello rizado?',
             'Sí, ayuda a alaciar o dar ondas; usa protector térmico y la temperatura adecuada a tu tipo de cabello.'),
        ],
    },
    {
        "category": 'belleza', "slug": 'planchas-y-rizadores', "name": 'Planchas y rizadores',
        "include": ['plancha de cabello', 'plancha para cabello', 'plancha alisadora', 'rizador', 'rizadora', 'onduladora', 'tenaza'],
        "exclude": ['pestanas'],
        "intro": (
            'Planchas para alaciar, tenazas, onduladoras de triple barril y rizadores automáticos para hacer ondas en casa.\n\n'
            'Las placas de cerámica o titanio reparten mejor el calor. Elige una temperatura según tu cabello: más baja para cabello fino o teñido, más alta para cabello grueso.'
        ),
        "faq": [
            ('¿Qué temperatura uso?',
             'Para cabello fino o teñido entre 150 y 180 °C; para cabello grueso puede ser más alta. Usa siempre protector térmico.'),
            ('¿El rizador automático es seguro?',
             'Sí, el cabello entra a una cámara y el aparato avisa cuando el rizo está listo, lo que reduce quemaduras.'),
        ],
    },
    {
        "category": 'belleza', "slug": 'rasuradoras-y-cortadoras', "name": 'Rasuradoras y cortadoras de cabello',
        "include": ['rasuradora', 'afeitadora', 'maquina de afeitar', 'cortadora de pelo', 'cortadora de cabello', 'patillera', 'trimmer', 'recortadora'],
        "exclude": [],
        "intro": (
            'Rasuradoras eléctricas, recortadoras de barba, patilleras, cortadoras de cabello y recortadoras de vello de nariz para arreglarte en casa.\n\n'
            'Revisa cuántos peines guía incluye y si es recargable. Para barba y cabello, una recortadora con varios largos te da más opciones.'
        ),
        "faq": [
            ('¿Se puede usar en la regadera?',
             'Solo las que dicen resistentes al agua o uso en húmedo; la ficha lo indica.'),
            ('¿Cuánto dura la batería?',
             'Varía según el modelo; en la ficha aparecen los minutos de uso por carga.'),
        ],
    },
    {
        "category": 'belleza', "slug": 'depiladoras', "name": 'Depiladoras',
        "include": ['depiladora', 'depilador', 'depilacion', 'ipl'],
        "exclude": [],
        "intro": (
            'Depiladoras eléctricas para piernas, axilas, cejas y rostro, con cabezales intercambiables y opción recargable para llevarlas de viaje.\n\n'
            'Las depiladoras faciales son pequeñas y discretas; para piernas conviene una con cabezal más ancho. Exfolia la piel un día antes para mejores resultados.'
        ),
        "faq": [
            ('¿Duele usar una depiladora eléctrica?',
             'Las que arrancan el vello pueden molestar las primeras veces; las de tipo rasuradora no duelen.'),
            ('¿Sirve para el rostro?',
             'Sí, las faciales están diseñadas para bozo, mejillas y cejas.'),
        ],
    },
    {
        "category": 'belleza', "slug": 'cuidado-facial', "name": 'Cuidado facial',
        "include": ['serum', 'tonico', 'mascarilla', 'crema facial', 'limpiador facial', 'contorno de ojos', 'masajeador facial', 'exfoliante', 'protector solar', 'bloqueador'],
        "exclude": [],
        "intro": (
            'Sérums, tónicos, mascarillas, cremas, contornos de ojos, protectores solares y aparatos de limpieza facial para armar tu rutina de cuidado de la piel.\n\n'
            'Una rutina básica tiene tres pasos: limpiar, hidratar y proteger del sol. Prueba cualquier producto nuevo en una zona pequeña antes de usarlo en todo el rostro.'
        ),
        "faq": [
            ('¿En qué orden aplico los productos?',
             'Primero limpiador, luego tónico, sérum, contorno de ojos, crema hidratante y, de día, protector solar.'),
            ('¿Sirven para piel sensible?',
             'Revisa los ingredientes en la ficha y haz una prueba en una zona pequeña antes de aplicarlo en todo el rostro.'),
        ],
    },
    {
        "category": 'belleza', "slug": 'cuidado-del-cabello', "name": 'Cuidado del cabello',
        "include": ['shampoo', 'champu', 'acondicionador', 'tratamiento capilar', 'aceite para cabello', 'tinte', 'crecimiento de cabello', 'minoxidil'],
        "exclude": ['mascota', 'mascotas', 'perro'],
        "intro": (
            'Shampoos, tratamientos, aceites, shampoos con tinte para cubrir canas y productos para el cabello maltratado o seco.\n\n'
            'Lee en la ficha el tipo de cabello para el que está hecho cada producto. Los shampoos con tinte se aplican como un shampoo normal y se dejan actuar unos minutos.'
        ),
        "faq": [
            ('¿El shampoo con tinte mancha?',
             'Puede manchar toallas o piel al aplicarlo; usa guantes y enjuaga bien. La ficha trae las instrucciones.'),
            ('¿Cada cuánto uso el tratamiento?',
             'Depende del producto; normalmente una o dos veces por semana. Sigue las indicaciones de la ficha.'),
        ],
    },
    {
        "category": 'belleza', "slug": 'perfumes', "name": 'Perfumes',
        "include": ['perfume', 'perfumes', 'fragancia', 'eau de', 'body mist', 'colonia'],
        "exclude": ['organizador'],
        "intro": (
            'Perfumes para dama y caballero, kits de varios aromas y fragancias de bolsillo para llevar en la bolsa o la mochila.\n\n'
            'Lee la descripción del aroma (floral, dulce, amaderado, cítrico) para saber si te va a gustar. Aplícalo en muñecas y cuello, sin frotar, para que dure más.'
        ),
        "faq": [
            ('¿Cuánto dura el aroma?',
             'Depende de la concentración y de tu piel. Aplicarlo sobre piel hidratada ayuda a que dure más.'),
            ('¿Los perfumes son originales?',
             'Cada ficha indica el producto exactamente como lo vende el proveedor; si dice réplica o inspirado en, no es la marca original.'),
        ],
    },
    {
        "category": 'belleza', "slug": 'blanqueamiento-dental', "name": 'Blanqueamiento e higiene dental',
        "include": ['blanqueador dental', 'blanqueamiento', 'blanqueador de dientes', 'cepillo dental', 'cepillo de dientes', 'irrigador'],
        "exclude": [],
        "intro": (
            'Kits de blanqueamiento con luz LED, pastas blanqueadoras, irrigadores bucales y cepillos eléctricos para una sonrisa más limpia.\n\n'
            'El irrigador limpia entre los dientes y alrededor de brackets donde el cepillo no llega. Si tienes sensibilidad dental, consulta con tu dentista antes de blanquear.'
        ),
        "faq": [
            ('¿El blanqueamiento daña el esmalte?',
             'Usado según las instrucciones es seguro para la mayoría. Si tienes sensibilidad o tratamientos dentales, consulta antes a tu dentista.'),
            ('¿El irrigador sirve con brackets?',
             'Sí, es muy útil para limpiar alrededor de brackets y puentes.'),
        ],
    },
    # ── salud_bienestar ───────────────────────────────────────────────────────
    {
        "category": 'salud_bienestar', "slug": 'suplementos', "name": 'Suplementos alimenticios',
        "include": ['suplemento', 'capsulas', 'colageno', 'biotina', 'magnesio', 'shilajit', 'berberina', 'vitamina', 'gomitas', 'gomas', 'omega', 'creatina', 'proteina'],
        "exclude": [],
        "intro": (
            'Colágeno, magnesio, biotina, vitaminas, shilajit, berberina, gomitas y otros suplementos alimenticios para complementar tu alimentación.\n\n'
            'Los suplementos no son medicamentos y no sustituyen una dieta equilibrada ni un tratamiento médico. Si estás embarazada, lactando o tomas medicamentos, consulta a tu médico antes de consumirlos.'
        ),
        "faq": [
            ('¿Los suplementos curan enfermedades?',
             'No. Son complementos de la alimentación; no previenen, curan ni tratan enfermedades. Consulta a tu médico ante cualquier padecimiento.'),
            ('¿Cómo los tomo?',
             'Sigue la dosis indicada en la etiqueta de cada producto y no la excedas.'),
        ],
    },
    {
        "category": 'salud_bienestar', "slug": 'masajeadores', "name": 'Masajeadores',
        "include": ['masajeador', 'pistola de masaje', 'pistola masajeadora', 'masaje'],
        "exclude": ['facial'],
        "intro": (
            'Pistolas de masaje para después del ejercicio, masajeadores de cuello y espalda, almohadas masajeadoras, electroestimuladores y masajeadores de pies para relajarte en casa.\n\n'
            'La pistola de masaje funciona bien en piernas, glúteos y espalda; para el cuello hay masajeadores en forma de U. Evita aplicarlos sobre huesos, heridas o zonas inflamadas.'
        ),
        "faq": [
            ('¿Cuánto tiempo uso la pistola de masaje?',
             'Entre uno y dos minutos por zona es suficiente; no la dejes fija en un punto.'),
            ('¿Puedo usarlo si tengo alguna lesión?',
             'Si tienes una lesión, marcapasos, embarazo o algún padecimiento, consulta primero a tu médico.'),
        ],
    },
    {
        "category": 'salud_bienestar', "slug": 'correctores-de-postura', "name": 'Correctores de postura',
        "include": ['corrector de postura', 'corrector postura', 'faja lumbar', 'soporte lumbar'],
        "exclude": [],
        "intro": (
            'Correctores de postura para espalda y hombros, fajas lumbares y soportes para quien pasa muchas horas sentado frente a la computadora o carga peso.\n\n'
            'Úsalo por ratos al principio, de 30 minutos a una hora, y ve aumentando. Elige la talla con la medida del pecho o la cintura que aparece en la ficha.'
        ),
        "faq": [
            ('¿Se nota debajo de la ropa?',
             'Los modelos delgados se pueden usar debajo de una playera o camisa holgada.'),
            ('¿Cuántas horas al día lo uso?',
             'Empieza con poco tiempo y aumenta poco a poco; no está hecho para dormir con él.'),
        ],
    },
    {
        "category": 'salud_bienestar', "slug": 'baumanometros-oximetros-y-termometros', "name": 'Baumanómetros, oxímetros y termómetros',
        "include": ['baumanometro', 'tensiometro', 'oximetro', 'glucometro', 'termometro', 'bascula', 'bascula corporal'],
        "exclude": ['cocina', 'precision', 'pocket', 'joyeria', 'gramera', 'comida'],
        "intro": (
            'Baumanómetros digitales de brazo y muñeca, oxímetros de dedo, termómetros infrarrojos y glucómetros para llevar un registro en casa.\n\n'
            'Estos aparatos ayudan a dar seguimiento, pero no reemplazan la consulta médica. Para medir la presión, siéntate tranquilo cinco minutos antes y apoya el brazo a la altura del corazón.'
        ),
        "faq": [
            ('¿Es mejor el baumanómetro de brazo o de muñeca?',
             'El de brazo suele ser más preciso; el de muñeca es más compacto para llevar.'),
            ('¿El termómetro infrarrojo necesita tocar la piel?',
             'No, mide a unos centímetros de la frente, ideal para niños.'),
        ],
    },
    {
        "category": 'salud_bienestar', "slug": 'fajas-y-moldeadores', "name": 'Fajas y moldeadores',
        "include": ['faja', 'fajas', 'chaleco reductor', 'cinturilla', 'moldeador', 'short reductor', 'chaleco'],
        "exclude": ['lumbar'],
        "intro": (
            'Fajas moldeadoras, chalecos de compresión, cinturillas y shorts reductores para usar bajo la ropa o al hacer ejercicio.\n\n'
            'La talla es lo más importante: mide tu cintura y cadera y compáralas con la tabla de la ficha. Una faja demasiado apretada incomoda y no ayuda más.'
        ),
        "faq": [
            ('¿Cómo elijo la talla?',
             'Mide tu cintura en la parte más angosta y compárala con la tabla de tallas de la ficha. Si quedas entre dos tallas, elige la mayor.'),
            ('¿Puedo hacer ejercicio con ella?',
             'Las de neopreno tipo sauna están pensadas para entrenar; las moldeadoras de tela, para el uso diario bajo la ropa.'),
        ],
    },
    # ── moda_accesorios ───────────────────────────────────────────────────────
    {
        "category": 'moda_accesorios', "slug": 'relojes', "name": 'Relojes',
        "include": ['reloj', 'relojes'],
        "exclude": ['inteligente', 'smartwatch', 'smart', 'despertador', 'pared', 'proyector'],
        "intro": (
            'Relojes para dama y caballero: análogos de acero, de piel, digitales deportivos y diseños elegantes para regalo.\n\n'
            'Revisa el diámetro de la caja (los de caballero suelen ser más grandes) y el material de la correa. Muchos relojes de acero permiten ajustar los eslabones.'
        ),
        "faq": [
            ('¿Son resistentes al agua?',
             'Depende del modelo; la ficha indica si aguanta salpicaduras o inmersión.'),
            ('¿Se puede ajustar la correa?',
             'Las de piel tienen varios orificios y las de acero se ajustan quitando eslabones; cualquier relojería lo hace en minutos.'),
        ],
    },
    {
        "category": 'moda_accesorios', "slug": 'mochilas-y-maletas', "name": 'Mochilas y maletas',
        "include": ['mochila', 'maleta', 'morral', 'bolso', 'cangurera', 'backpack'],
        "exclude": ['bebes', 'porta bebes', 'mascotas', 'bolsas'],
        "intro": (
            'Mochilas para la escuela, el trabajo y los viajes, maletas de mano, bolsos deportivos, cangureras y mochilas pañaleras.\n\n'
            'Para viajar en avión, revisa las medidas máximas de equipaje de mano de tu aerolínea. Para la laptop, busca un compartimento acolchado.'
        ),
        "faq": [
            ('¿Cabe una laptop?',
             'Las que lo indican traen compartimento acolchado; la ficha dice hasta qué tamaño de pantalla.'),
            ('¿Sirve como equipaje de mano?',
             'Compara las medidas de la ficha con las que permite tu aerolínea.'),
        ],
    },
    {
        "category": 'moda_accesorios', "slug": 'lentes-de-sol', "name": 'Lentes de sol',
        "include": ['lentes de sol', 'lentes', 'gafas'],
        "exclude": ['bluetooth', 'contacto', 'camara', 'lupa', 'vr', 'realidad virtual'],
        "intro": (
            'Lentes de sol polarizados, lentes para manejar de noche, lentes fotocromáticos que se oscurecen con el sol y modelos de moda para dama y caballero.\n\n'
            'Los polarizados reducen el reflejo del sol en el pavimento y el agua, útiles para manejar. Revisa que indiquen protección UV400.'
        ),
        "faq": [
            ('¿Qué diferencia hay entre polarizado y protección UV?',
             'La protección UV cuida tus ojos de la radiación; el polarizado reduce los reflejos. Lo ideal es que tenga ambos.'),
            ('¿Los lentes para manejar de noche son seguros?',
             'Reducen el deslumbramiento de las luces de otros autos; no aumentan la visión en la oscuridad.'),
        ],
    },
    {
        "category": 'moda_accesorios', "slug": 'joyeria', "name": 'Joyería y accesorios',
        "include": ['pulsera', 'collar', 'aretes', 'anillo', 'cadena', 'dije'],
        "exclude": ['lubricante', 'cadenas', 'bicicleta', 'perro', 'mascota', 'mascotas', 'fumar'],
        "intro": (
            'Collares, pulseras, aretes, anillos y dijes para regalar o para ti, con estuches listos para regalo en muchos modelos.\n\n'
            'Revisa el material en la ficha: acero inoxidable y oro laminado resisten mejor el uso diario. Para regalar, los que traen caja ahorran envoltura.'
        ),
        "faq": [
            ('¿La joyería se pone negra?',
             'El acero inoxidable y el oro laminado de buena calidad tardan mucho en oscurecerse. Evita perfumes y agua de alberca para cuidarla.'),
            ('¿Incluye caja de regalo?',
             'Algunos modelos sí; la ficha lo menciona.'),
        ],
    },
    # ── deporte_fitness ───────────────────────────────────────────────────────
    {
        "category": 'deporte_fitness', "slug": 'ejercicio-en-casa', "name": 'Ejercicio en casa',
        "include": ['mancuerna', 'ligas', 'banda elastica', 'ejercitador', 'abdominales', 'cuerda para saltar', 'tapete de yoga', 'barra de dominadas', 'rueda abdominal'],
        "exclude": ['pelvico', 'pulmones', 'respiratorio', 'crema', 'adelgazante'],
        "intro": (
            'Mancuernas, ligas de resistencia, ruedas abdominales, ejercitadores y accesorios para entrenar en casa sin pagar gimnasio.\n\n'
            'Con unas ligas de resistencia y un par de mancuernas ajustables puedes trabajar todo el cuerpo. Empieza con poco peso y aumenta poco a poco.'
        ),
        "faq": [
            ('¿Qué necesito para empezar a entrenar en casa?',
             'Unas ligas de resistencia, un tapete y mancuernas ligeras cubren la mayoría de los ejercicios.'),
            ('¿Las ligas tienen diferentes resistencias?',
             'Sí, los sets suelen traer varias; la ficha indica el nivel de cada una.'),
        ],
    },
    {
        "category": 'deporte_fitness', "slug": 'rodilleras-y-soportes', "name": 'Rodilleras y soportes',
        "include": ['rodillera', 'tobillera', 'munequera', 'codera', 'soporte de rodilla'],
        "exclude": [],
        "intro": (
            'Rodilleras, tobilleras, muñequeras y coderas de compresión para hacer deporte, caminar o trabajar con más soporte.\n\n'
            'Elige la talla con la medida que pide la ficha (normalmente alrededor de la rodilla o el tobillo). Si tienes una lesión, consulta a un médico o fisioterapeuta.'
        ),
        "faq": [
            ('¿Cómo sé mi talla?',
             'Mide la circunferencia de la articulación como indica la ficha y compárala con la tabla.'),
            ('¿Puedo usarla todo el día?',
             'Las de compresión se pueden usar varias horas; quítatela si sientes adormecimiento u hormigueo.'),
        ],
    },
    # ── herramientas ──────────────────────────────────────────────────────────
    {
        "category": 'herramientas', "slug": 'taladros-y-atornilladores', "name": 'Taladros y atornilladores',
        "include": ['taladro', 'atornillador', 'rotomartillo', 'desarmador electrico', 'brocas'],
        "exclude": ['podadora', 'sembrar', 'sierra'],
        "intro": (
            'Taladros inalámbricos, rotomartillos, desarmadores eléctricos recargables y juegos de brocas para colgar repisas, armar muebles y hacer reparaciones en casa.\n\n'
            'Para concreto necesitas función de percusión o rotomartillo; para madera y metal basta un taladro normal. Revisa si incluye una o dos baterías.'
        ),
        "faq": [
            ('¿Sirve para perforar concreto?',
             'Solo los que tienen percusión o son rotomartillos, con broca para concreto.'),
            ('¿Incluye baterías y cargador?',
             'La ficha indica cuántas baterías y qué accesorios trae en la caja.'),
        ],
    },
    {
        "category": 'herramientas', "slug": 'hidrolavadoras-y-compresores', "name": 'Hidrolavadoras y compresores',
        "include": ['hidrolavadora', 'compresor', 'pistola de agua a presion', 'inflador', 'lavadora a presion'],
        "exclude": [],
        "intro": (
            'Hidrolavadoras inalámbricas para lavar el auto, la cochera o el patio, y compresores portátiles para inflar llantas de auto, moto, bici y balones.\n\n'
            'Las hidrolavadoras portátiles con batería pueden tomar agua de una cubeta, útiles donde no hay llave cerca. Los compresores de 12 V se conectan al encendedor del auto.'
        ),
        "faq": [
            ('¿Necesito llave de agua para la hidrolavadora?',
             'Las portátiles suelen succionar agua de una cubeta o garrafón; la ficha lo indica.'),
            ('¿El compresor sirve para llantas de camioneta?',
             'Revisa la presión máxima en la ficha; para llantas grandes tarda más.'),
        ],
    },
    {
        "category": 'herramientas', "slug": 'juegos-de-herramientas', "name": 'Juegos de herramientas',
        "include": ['juego de herramientas', 'kit de herramientas', 'caja de herramientas', 'juego de llaves', 'juego de desarmadores', 'desarmador'],
        "exclude": [],
        "intro": (
            'Juegos de llaves y dados, desarmadores de precisión y estuches con lo básico para tener en casa o en el auto.\n\n'
            'Un juego con dados métricos y estándar cubre la mayoría de las reparaciones. Los desarmadores de precisión sirven para lentes, controles y celulares.'
        ),
        "faq": [
            ('¿Trae estuche?',
             'La mayoría de los juegos viene en estuche rígido; la ficha muestra el contenido completo.'),
            ('¿Son medidas métricas o estándar?',
             'La ficha detalla las medidas incluidas en cada juego.'),
        ],
    },
    # ── vehiculos ─────────────────────────────────────────────────────────────
    {
        "category": 'vehiculos', "slug": 'accesorios-para-auto', "name": 'Accesorios para auto',
        "include": ['para auto', 'para carro', 'para coche', 'auto', 'automovil', 'carro'],
        "exclude": ['control remoto', 'juguete', 'escala'],
        "intro": (
            'Aspiradoras para auto, soportes de celular, organizadores, ceras y pulidores, cargadores de batería, ventiladores, luces LED y accesorios para cuidar tu coche.\n\n'
            'Antes de pedir accesorios eléctricos, revisa si se conectan al encendedor de 12 V o si son recargables. Para ceras y pulidores, aplica a la sombra con la pintura fría.'
        ),
        "faq": [
            ('¿Funcionan en cualquier auto?',
             'Los que se conectan al encendedor funcionan en cualquier auto con toma de 12 V. Otros accesorios indican la compatibilidad en la ficha.'),
            ('¿Cómo aplico la cera?',
             'Con el auto limpio, seco y a la sombra, en capas delgadas, y retira con un paño de microfibra.'),
        ],
    },
    {
        "category": 'vehiculos', "slug": 'accesorios-para-moto', "name": 'Accesorios para moto',
        "include": ['moto', 'motocicleta', 'casco'],
        "exclude": ['suplemento', 'metabolismo'],
        "intro": (
            'Intercomunicadores bluetooth para casco, audífonos para casco, cojines, cubiertas y accesorios para quienes andan en moto todos los días.\n\n'
            'En intercomunicadores revisa el alcance entre cascos y si permiten música y llamadas. Para el sol y la lluvia, una cubierta protege el asiento y la pintura.'
        ),
        "faq": [
            ('¿El intercomunicador sirve en cualquier casco?',
             'Sí, se pega o se sujeta con clip en la mayoría de los cascos cerrados y abatibles.'),
            ('¿Se puede escuchar música?',
             'Sí, se enlaza por bluetooth al celular para música, llamadas y GPS.'),
        ],
    },
    # ── juguetes ──────────────────────────────────────────────────────────────
    {
        "category": 'juguetes', "slug": 'juguetes-a-control-remoto', "name": 'Juguetes a control remoto',
        "include": ['control remoto', 'rc', 'dron', 'drone'],
        "exclude": ['tv', 'television', 'luces', 'led'],
        "intro": (
            'Drones con cámara, autos todoterreno, lanchas y helicópteros a control remoto para niños y adultos.\n\n'
            'Revisa la edad recomendada, cuántos minutos dura la batería y si incluye pilas o batería recargable. Para drones, empieza en espacios abiertos y sin viento.'
        ),
        "faq": [
            ('¿Cuánto dura la batería?',
             'La mayoría vuela o corre entre 8 y 20 minutos por carga; algunos traen batería extra.'),
            ('¿Los drones necesitan permiso?',
             'Los drones pequeños de juguete se usan para recreación; evita volarlos cerca de aeropuertos o de personas.'),
        ],
    },
    {
        "category": 'juguetes', "slug": 'pistolas-de-hidrogel-y-burbujas', "name": 'Pistolas de hidrogel y burbujas',
        "include": ['pistola de hidrogel', 'hidrogel', 'pistola de agua', 'pistola de burbujas', 'burbujas', 'gel blaster', 'pistola de juguete', 'ametralladora', 'lanzador de agua'],
        "exclude": ['pintura', 'clavos', 'arena', 'silicon', 'calor', 'masaje', 'masajeadora', 'alta presion', 'karcher', 'lavar', 'nivel', 'laser'],
        "intro": (
            'Pistolas de hidrogel, lanzadores de agua y pistolas de burbujas para jugar en el patio, el parque o en las fiestas.\n\n'
            'Las de hidrogel usan bolitas que se hidratan en agua; usa siempre lentes de protección y nunca apuntes a la cara. Revisa la edad recomendada en la ficha.'
        ),
        "faq": [
            ('¿Las bolitas de hidrogel vienen incluidas?',
             'La mayoría trae un paquete; la ficha indica el contenido.'),
            ('¿Son seguras para niños?',
             'Respeta la edad recomendada, usa lentes de protección y supervisa el juego.'),
        ],
    },
    # ── mascotas ──────────────────────────────────────────────────────────────
    {
        "category": 'mascotas', "slug": 'productos-para-mascotas', "name": 'Productos para mascotas',
        "include": ['perro', 'perros', 'mascota', 'mascotas', 'gato', 'gatos', 'rascador', 'arenero', 'correa para perro'],
        "exclude": ['hidraulico', 'ojos de gato', 'alcancia', 'ventana', 'altavoz', 'bocina'],
        "intro": (
            'Correas, bebederos, cepillos quitapelo, rascadores, camas y accesorios para perros y gatos.\n\n'
            'Para correas y arneses, elige según el peso de tu mascota. Los cepillos de cerdas finas ayudan a retirar el pelo muerto y reducen el que queda en sillones y ropa.'
        ),
        "faq": [
            ('¿Qué correa necesito para mi perro?',
             'Elige según el peso que indica la ficha; las retráctiles son prácticas para paseos tranquilos.'),
            ('¿Los bebederos automáticos necesitan luz?',
             'Algunos son eléctricos por USB y otros funcionan por gravedad; la ficha lo indica.'),
        ],
    },
    # ── bebes ─────────────────────────────────────────────────────────────────
    {
        "category": 'bebes', "slug": 'productos-para-bebe', "name": 'Productos para bebé',
        "include": ['bebe', 'bebes', 'biberon', 'lactancia', 'panal', 'sacaleches', 'extractor de leche'],
        "exclude": [],
        "intro": (
            'Calentadores de biberones, accesorios de lactancia, monitores, juguetes, arneses de seguridad y artículos prácticos para los primeros años.\n\n'
            'Revisa la edad recomendada de cada producto y lava los artículos que van a la boca antes del primer uso.'
        ),
        "faq": [
            ('¿Los calentadores de biberones sirven para cualquier biberón?',
             'La mayoría acepta biberones estándar y de boca ancha; revisa las medidas en la ficha.'),
            ('¿Son seguros los materiales?',
             'Revisa en la ficha si indica libre de BPA para los artículos que van a la boca.'),
        ],
    },
]
