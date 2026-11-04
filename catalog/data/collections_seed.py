"""
Colecciones iniciales (octubre 2026), elegidas por los tipos de producto con
más referencias en el catálogo. Cada texto está escrito para su tipo de
producto, sin plantillas: Google trata el texto repetido con plantilla como
contenido hecho en masa.

`manage.py refresh_collections --load-seed` las crea si no existen (no pisa
lo editado en el admin, salvo con --overwrite-seed) y publica solo las que
tienen al menos MIN_PRODUCTS_TO_PUBLISH productos.

Campos: category (clave de la categoría de la tienda), slug, name, include,
exclude, intro (párrafos separados por línea en blanco), faq [(pregunta,
respuesta)].
"""

SEED = [
    # ── Cocina ────────────────────────────────────────────────────────────────
    {
        "category": "cocina", "slug": "organizadores-de-cocina", "name": "Organizadores de cocina",
        "include": ["organizador cocina", "organizador de cocina", "organizador nevera", "organizador de nevera",
                    "organizador especias", "especiero", "organizador huevos", "organizador de huevos",
                    "organizador alacena", "organizador cubiertos", "organizador de cubiertos", "organizador platos",
                    "organizador de platos", "organizador ollas", "organizador tapas", "organizador lavaplatos"],
        "exclude": [],
        "intro": (
            "Una cocina pequeña rinde el doble cuando cada cosa tiene su lugar. Aquí están los organizadores para "
            "la nevera, la alacena, los cajones y el mesón: huevera para la puerta de la nevera, especieros "
            "giratorios, separadores para cubiertos, racks para tapas y ollas, y canastas que aprovechan el espacio "
            "debajo del lavaplatos.\n\n"
            "Antes de elegir, mide el espacio donde lo vas a poner: alto de la repisa, fondo del gabinete o ancho "
            "del cajón. En cada producto encuentras las medidas y el material, y si tienes dudas sobre si te cabe, "
            "nos escribes por WhatsApp con la medida y te confirmamos."
        ),
        "faq": [
            ("¿Qué organizador sirve para una nevera pequeña?",
             "Los de acrílico transparente y poca profundidad, como las hueveras y las canastas apilables: dejan ver "
             "lo que hay adentro y no roban espacio. Revisa el ancho de la bandeja antes de pedir."),
            ("¿Los organizadores de plástico resisten la humedad del lavaplatos?",
             "Sí, los de plástico o acrílico no se oxidan. Los metálicos para debajo del lavaplatos traen pintura "
             "epóxica o acero inoxidable; lo verás indicado en la ficha del producto."),
        ],
    },
    {
        "category": "cocina", "slug": "dispensadores-de-agua", "name": "Dispensadores de agua",
        "include": ["dispensador agua", "dispensador de agua", "dispensador electrico", "bomba de agua", "bomba agua botellon",
                    "dispensador botellon"],
        "exclude": ["jabon", "shampoo", "papel"],
        "intro": (
            "Servir agua del botellón sin levantarlo es la razón por la que más se piden estos productos. Hay "
            "bombas eléctricas recargables por USB que se ponen encima del botellón, dispensadores de mesa y "
            "bases con llave para dejar el botellón boca abajo.\n\n"
            "Fíjate en el tipo de boca de tu garrafón, en cuántos días dura la "
            "batería con una carga y en si el tubo llega al fondo de un botellón de 20 litros."
        ),
        "faq": [
            ("¿La bomba eléctrica sirve para cualquier botellón?",
             "Sirve para los botellones estándar de 18 a 20 litros. Si el tuyo es de otra marca o tamaño, mándanos "
             "una foto por WhatsApp y te decimos si encaja."),
            ("¿Cuánto dura la batería de un dispensador recargable?",
             "Depende del modelo; la mayoría alcanza para varios botellones con una carga por USB. El dato exacto "
             "está en la descripción de cada producto."),
        ],
    },
    {
        "category": "cocina", "slug": "escurridores-de-platos", "name": "Escurridores de platos",
        "include": ["escurridor", "escurridor platos", "escurridor de platos", "secaplatos", "seca platos"],
        "exclude": [],
        "intro": (
            "El escurridor correcto depende del espacio que te quede libre: los de dos niveles ocupan poco mesón, "
            "los que van encima del lavaplatos dejan caer el agua directo al desagüe y los plegables se guardan "
            "cuando no los usas.\n\n"
            "Revisa el largo total frente al ancho de tu lavaplatos, si trae bandeja para recoger el agua y si "
            "tiene espacio para vasos y cubiertos. Los de acero inoxidable aguantan mejor la humedad diaria."
        ),
        "faq": [
            ("¿Cómo sé si el escurridor que va sobre el lavaplatos me sirve?",
             "Mide el ancho exterior de tu lavaplatos y compáralo con el rango ajustable del escurridor que aparece "
             "en la ficha. Si queda en el límite, escríbenos antes de pedir."),
            ("¿Se oxidan?",
             "Los de acero inoxidable y los de plástico no. Los de metal pintado pueden marcarse con el tiempo si "
             "la pintura se raya."),
        ],
    },
    {
        "category": "cocina", "slug": "utensilios-de-cocina", "name": "Utensilios de cocina",
        "include": ["utensilios cocina", "utensilios de cocina", "juego utensilios", "set utensilios", "juego de utensilios",
                    "espatula", "cucharon", "pinzas cocina"],
        "exclude": ["facial", "ultrasonica", "unas"],
        "intro": (
            "Espátulas, cucharones, pinzas y juegos completos con su base. Si vas a renovar todo de una vez, los "
            "sets de silicona traen las piezas más usadas y no rayan sartenes antiadherentes.\n\n"
            "La silicona aguanta bien el calor de la estufa y se lava fácil; la madera es más liviana pero pide "
            "secado. En cada set aparece cuántas piezas incluye, para que compares bien."
        ),
        "faq": [
            ("¿Los utensilios de silicona sirven para sartenes antiadherentes?",
             "Sí, es su principal ventaja: no rayan el recubrimiento. Evita dejarlos apoyados dentro de la sartén "
             "caliente por mucho tiempo."),
            ("¿Se pueden lavar en lavavajillas?",
             "Los de silicona y acero, en general sí. Los que tienen mango de madera es mejor lavarlos a mano."),
        ],
    },
    {
        "category": "cocina", "slug": "sartenes-y-ollas", "name": "Sartenes y ollas",
        "include": ["sarten", "sartenes", "olla", "bateria de cocina", "bateria cocina", "juego de ollas", "juego ollas",
                    "wok", "parrilla"],
        "exclude": ["arrocera", "olla arrocera", "freidora", "electrica", "cera", "organizador"],
        "intro": (
            "Sartenes antiadherentes, ollas, woks, parrillas para estufa y baterías completas. Para el día a día lo "
            "más práctico es una sartén de 24 a 28 cm con recubrimiento antiadherente; para cocinar para varias "
            "personas, una batería con ollas de distintos tamaños.\n\n"
            "Antes de pedir, mira si tu estufa es de gas, eléctrica o de inducción: no todas las sartenes sirven "
            "para inducción y en la ficha está indicado cuáles sí."
        ),
        "faq": [
            ("¿Cómo cuido una sartén antiadherente?",
             "Usa utensilios de silicona o madera, no la calientes vacía a fuego alto y lávala con esponja suave. "
             "Así el recubrimiento dura mucho más."),
            ("¿Sirven para estufa de inducción?",
             "Solo las que tienen base magnética. Si la ficha no lo menciona, pregúntanos por WhatsApp antes de "
             "comprar."),
        ],
    },
    {
        "category": "cocina", "slug": "licuadoras-portatiles", "name": "Licuadoras portátiles",
        "include": ["licuadora portatil", "licuadora recargable", "licuadora personal", "licuadora usb", "vaso licuadora"],
        "exclude": [],
        "intro": (
            "Las licuadoras portátiles se cargan por USB y licúan directamente en el vaso en que vas a tomar: "
            "sirven para batidos, jugos de fruta blanda y proteína en polvo, en la casa, la oficina o el gimnasio.\n\n"
            "Compara la capacidad del vaso (de 300 a 600 ml), cuántas licuadas da una carga y el número de "
            "cuchillas. Para hielo entero o frutas muy duras es mejor una licuadora de mesa."
        ),
        "faq": [
            ("¿Una licuadora portátil tritura hielo?",
             "La mayoría puede con hielo picado o en trozos pequeños mezclado con líquido; para cubos enteros se "
             "queda corta."),
            ("¿Cómo se lava?",
             "Llénala hasta la mitad con agua y una gota de jabón, enciéndela unos segundos y enjuágala. La base con "
             "el motor no se sumerge."),
        ],
    },
    {
        "category": "cocina", "slug": "cuchillos-y-afiladores", "name": "Cuchillos y afiladores",
        "include": ["cuchillo", "juego cuchillos", "set cuchillos", "afilador", "afilador cuchillos", "afilador de cuchillos",
                    "tabla de picar", "tabla picar"],
        "exclude": [],
        "intro": (
            "Juegos de cuchillos con base, cuchillos de chef, afiladores manuales y eléctricos, y tablas de picar. "
            "Un cuchillo bien afilado corta con menos fuerza y es más seguro que uno sin filo.\n\n"
            "Los afiladores de ranuras son los más fáciles de usar en casa: pasas el cuchillo unas veces por la "
            "ranura gruesa y luego por la fina. En la ficha de cada juego verás cuántas piezas trae y de qué acero son."
        ),
        "faq": [
            ("¿Cada cuánto hay que afilar los cuchillos?",
             "Con uso diario, una pasada por el afilador cada una o dos semanas mantiene el filo. Si ya no cortan un "
             "tomate sin aplastarlo, es momento de afilarlos."),
            ("¿Qué tabla de picar es mejor?",
             "Las de madera cuidan el filo y las de plástico se lavan fácil. Lo ideal es tener una aparte para "
             "carnes crudas."),
        ],
    },
    {
        "category": "cocina", "slug": "loncheras-electricas", "name": "Loncheras eléctricas",
        "include": ["lonchera electrica", "lonchera termica", "lonchera calentadora", "calentador de comida",
                    "lonchera"],
        "exclude": ["nina", "nino", "infantil"],
        "intro": (
            "Las loncheras eléctricas calientan el almuerzo sin microondas: se conectan a la corriente de la "
            "oficina, o al encendedor del carro en los modelos de 12 V, y en 20 a 40 minutos la comida queda "
            "caliente.\n\n"
            "Revisa si trae recipiente de acero inoxidable desmontable, la capacidad y si incluye cable para carro. "
            "Son útiles para quien trabaja en obra, en ruta o en oficinas sin cocina."
        ),
        "faq": [
            ("¿Cuánto se demora en calentar?",
             "Entre 20 y 40 minutos según el modelo y la cantidad de comida. Conéctala un rato antes de la hora del "
             "almuerzo."),
            ("¿Se puede usar en el carro?",
             "Sí, si el modelo trae cable de 12 V para el encendedor. Está indicado en la ficha."),
        ],
    },
    {
        "category": "cocina", "slug": "termos-y-botellas", "name": "Termos y botellas",
        "include": ["termo", "botella termica", "botella termo", "vaso termico", "mug termico", "termo cafe",
                    "botella de agua", "botella agua", "botella motivacional"],
        "exclude": ["termometro", "cepillo"],
        "intro": (
            "Termos para café, vasos térmicos con tapa, botellas para el gimnasio y botellas motivacionales con "
            "marcas de horario para recordarte tomar agua.\n\n"
            "Para conservar temperatura por horas busca doble pared de acero inoxidable al vacío; para el gimnasio, "
            "una botella liviana de boca ancha que se lave fácil. La capacidad en mililitros está en cada ficha."
        ),
        "faq": [
            ("¿Cuánto tiempo mantiene el calor un termo de acero?",
             "Los de doble pared al vacío suelen mantener bebidas calientes varias horas. El tiempo exacto depende "
             "del modelo y está en su descripción."),
            ("¿Puedo echar bebidas con gas o jugos ácidos?",
             "En los de acero inoxidable sí. Evita leche dejada por muchas horas y lávalo el mismo día."),
        ],
    },
    {
        "category": "cocina", "slug": "picadores-y-ralladores", "name": "Picadores y ralladores",
        "include": ["picador", "picadora", "rallador", "mandolina", "cortador verduras", "cortador de verduras",
                    "procesador alimentos", "procesador de alimentos", "triturador", "molino"],
        "exclude": ["pelo", "unas", "hielo", "cafe electrico", "viento", "jardin", "decorativo"],
        "intro": (
            "Picar cebolla, tomate y ajo sin llorar ni ensuciar la tabla es lo que resuelven estos productos: "
            "picadores de cuerda, picadoras eléctricas pequeñas, mandolinas para tajadas parejas, ralladores y "
            "molinos de especias.\n\n"
            "Para el uso diario, un picador de cuerda o eléctrico de 250 a 500 ml basta. Las mandolinas cortan muy "
            "rápido: úsalas siempre con el protector para los dedos que viene incluido."
        ),
        "faq": [
            ("¿Qué es mejor, picador manual o eléctrico?",
             "El manual de cuerda no necesita carga y es más barato; el eléctrico pica más rápido y parejo. Para "
             "cantidades pequeñas cualquiera de los dos sirve."),
            ("¿Se pueden lavar las cuchillas?",
             "Sí, se desmontan. Lávalas con cepillo y con cuidado, nunca pasando la mano por el filo."),
        ],
    },

    {
        "category": "cocina", "slug": "basculas-y-grameras", "name": "Básculas y grameras digitales",
        "include": ["bascula", "gramera", "pesa digital", "balanza digital", "balanza gramera"],
        "exclude": ["pila", "pilas", "repuesto"],
        "intro": (
            "Grameras para pesar ingredientes, porciones o café, básculas de cocina de hasta 10 kg, básculas de "
            "baño, pesas para equipaje y balanzas de precisión para joyería con divisiones de 0,01 g.\n\n"
            "Elige por dos números: la capacidad máxima y la precisión. Para recetas basta con divisiones de 1 g; "
            "para joyas, semillas o suplementos busca 0,01 g. La función de tara descuenta el peso del recipiente."
        ),
        "faq": [
            ("¿Qué pilas usan?",
             "La mayoría usan pilas AAA o de botón CR2032, y algunas se cargan por USB. Está indicado en cada ficha."),
            ("¿Para qué sirve el botón de tara?",
             "Pone la pantalla en cero con el recipiente encima, para que solo se pese lo que agregas."),
        ],
    },
    {
        "category": "cocina", "slug": "espumadores-de-leche", "name": "Espumadores de leche",
        "include": ["espumador", "batidor de leche", "batidor espumador"],
        "exclude": ["shampoo", "champu", "pistola", "carro", "auto", "moto", "lavado", "desengrasa", "desengrasante",
                    "jabon", "estufa", "donas", "fundidora", "cubiertos", "waflera"],
        "intro": (
            "Espumadores de mano a pilas o recargables y batidores eléctricos para hacer espuma de leche para el "
            "capuchino, el latte o el chocolate, y también para mezclar proteína, café instantáneo o huevos.\n\n"
            "La leche fría y entera hace más espuma; las bebidas vegetales espuman menos. Introduce el batidor "
            "antes de encenderlo para no salpicar y lávalo bajo el chorro de agua, sin mojar el mango."
        ),
        "faq": [
            ("¿Sirve para leche caliente?",
             "Sí, en un vaso o taza alto. Con leche tibia (no hirviendo) la espuma dura más."),
            ("¿Cuánto dura la carga de los recargables?",
             "Varias semanas de uso diario; se cargan por cable USB."),
        ],
    },

    # ── Hogar ─────────────────────────────────────────────────────────────────
    {
        "category": "hogar", "slug": "organizadores-de-bano", "name": "Organizadores de baño",
        "include": ["organizador bano", "organizador de bano", "estante bano", "estante de bano", "repisa bano",
                    "organizador ducha", "organizador de ducha", "esquinero ducha", "mueble bano", "mueble de bano",
                    "organizador sanitario", "organizador inodoro"],
        "exclude": [],
        "intro": (
            "En un baño pequeño, el espacio útil está encima del sanitario, en las esquinas de la ducha y detrás de "
            "la puerta. Aquí hay estantes que van sobre el inodoro, esquineros para champú y jabón, repisas con "
            "adhesivo que no requieren taladro y muebles delgados para toallas.\n\n"
            "Mide el ancho del sanitario y la altura disponible antes de pedir un estante de piso. Los adhesivos "
            "funcionan bien sobre baldosa lisa y limpia; en pared rugosa es mejor un modelo con tornillos."
        ),
        "faq": [
            ("¿Las repisas con adhesivo aguantan peso?",
             "Aguantan frascos de champú y jabón si la baldosa está lisa, limpia y seca al pegarlas, y si esperas "
             "unas horas antes de cargarlas. Para objetos pesados usa tornillos."),
            ("¿Se oxidan con la humedad de la ducha?",
             "Los de plástico, acrílico y acero inoxidable no. En la ficha está el material de cada uno."),
        ],
    },
    {
        "category": "hogar", "slug": "organizadores-de-ropa-y-closet", "name": "Organizadores de ropa y clóset",
        "include": ["organizador ropa", "organizador de ropa", "organizador closet", "organizador de closet", "closet",
                    "ropero", "armario", "organizador cajon", "organizador de cajon", "bolsa al vacio", "bolsas al vacio",
                    "perchero", "ganchos ropa"],
        "exclude": ["zapatos", "zapatero"],
        "intro": (
            "Clósets de tela armables, percheros, cajones divisores, bolsas al vacío y organizadores colgantes para "
            "aprovechar cada repisa. Son la salida más económica cuando la ropa ya no cabe o vives en arriendo y no "
            "quieres hacer obra.\n\n"
            "Los clósets de tela se arman en minutos y se desarman para trasteos; revisa alto, ancho y cuántos "
            "cuerpos tiene. Las bolsas al vacío reducen mucho el volumen de cobijas y ropa de temporada."
        ),
        "faq": [
            ("¿Cuánto peso aguanta un clóset de tela?",
             "Depende de la estructura; cada barra soporta la ropa colgada normal de una persona. El dato de cada "
             "modelo está en su ficha."),
            ("¿Las bolsas al vacío necesitan aspiradora?",
             "La mayoría se cierran con aspiradora o con la bomba manual que traen algunos sets. Revisa qué incluye "
             "el que vas a pedir."),
        ],
    },
    {
        "category": "hogar", "slug": "zapateros", "name": "Zapateros",
        "include": ["zapatero", "organizador zapatos", "organizador de zapatos", "organizador zapatero", "mueble zapatos",
                    "zapatera"],
        "exclude": [],
        "intro": (
            "Zapateros de varios niveles, de tela con cierre, metálicos armables, para detrás de la puerta y cajas "
            "apilables transparentes. El número de niveles define cuántos pares caben: un zapatero de 4 niveles "
            "guarda entre 12 y 16 pares de adulto.\n\n"
            "Mide el espacio donde lo vas a poner, sobre todo el fondo: los tenis grandes necesitan unos 30 cm. Los "
            "de tela protegen del polvo; los abiertos ventilan mejor."
        ),
        "faq": [
            ("¿Cuántos pares caben en un zapatero?",
             "Cada ficha indica la capacidad. Como referencia, cada nivel de 60 cm guarda tres o cuatro pares de "
             "adulto."),
            ("¿Es difícil de armar?",
             "No, la mayoría se arma a presión, sin herramientas, en pocos minutos."),
        ],
    },
    {
        "category": "hogar", "slug": "lamparas-solares", "name": "Lámparas solares",
        "include": ["lampara solar", "luz solar", "reflector solar", "foco solar", "farol solar", "aplique solar",
                    "luces solares", "panel solar"],
        "exclude": ["camara"],
        "intro": (
            "Las lámparas solares se cargan con el sol del día y se encienden solas al oscurecer, sin cables ni "
            "factura de luz. Sirven para patios, antejardines, fincas, caminos y fachadas.\n\n"
            "Para alumbrar una zona grande busca reflectores con panel separado y control remoto; para marcar un "
            "camino, estacas solares. Muchas traen sensor de movimiento: quedan tenues y suben la intensidad al "
            "detectar a alguien. Ubica el panel donde reciba sol directo varias horas."
        ),
        "faq": [
            ("¿Funcionan en días nublados?",
             "Sí, cargan menos y duran menos encendidas esa noche. Con sol directo de mañana y tarde rinden toda "
             "la noche."),
            ("¿Necesitan instalación eléctrica?",
             "No. Se fijan con tornillos o estaca y funcionan con la batería que carga el panel."),
        ],
    },
    {
        "category": "hogar", "slug": "lamparas-led-y-decorativas", "name": "Lámparas LED y decorativas",
        "include": ["lampara led", "lampara decorativa", "lampara luna", "lampara de mesa", "lampara mesa",
                    "lampara escritorio", "lampara de noche", "lampara noche", "lampara colgante", "lampara de pie",
                    "lampara recargable", "velador"],
        "exclude": ["solar", "unas", "uv", "secado", "camara"],
        "intro": (
            "Lámparas de mesa y escritorio, lámparas luna, de noche para el cuarto de los niños, colgantes y "
            "recargables sin cable. En las LED el consumo es mínimo y muchas permiten cambiar entre luz blanca, "
            "cálida y colores.\n\n"
            "Para estudiar o trabajar conviene luz blanca regulable y brazo flexible; para ambientar un cuarto, "
            "luz cálida o RGB con control. Las recargables por USB se pueden mover a cualquier lugar."
        ),
        "faq": [
            ("¿Cuánto dura la batería de una lámpara recargable?",
             "Depende del brillo elegido; en la ficha de cada modelo está la autonomía aproximada."),
            ("¿Qué luz es mejor para leer?",
             "Una luz blanca neutra o cálida, regulable, a un lado del libro para evitar reflejos."),
        ],
    },
    {
        "category": "hogar", "slug": "cintas-y-luces-led", "name": "Cintas y luces LED",
        "include": ["cinta led", "cintas led", "luces led", "tira led", "luz led rgb", "manguera led", "luces navidad",
                    "luces de navidad", "luces decorativas", "cortina de luces", "luces de hadas", "luces cascada"],
        "exclude": ["solar"],
        "intro": (
            "Cintas LED RGB para el cuarto, la sala o detrás del televisor, cortinas y cascadas de luces, luces de "
            "hadas y mangueras LED para fachadas. Muchas se controlan desde el celular o con control remoto y "
            "cambian de color con la música.\n\n"
            "Mide el largo que necesitas antes de pedir: la longitud total está en la ficha. Revisa también si se "
            "conecta a USB o a enchufe y si sirve para exteriores."
        ),
        "faq": [
            ("¿Las cintas LED se pueden cortar?",
             "La mayoría sí, por las marcas que traen cada cierto tramo. Corta solo por esas líneas."),
            ("¿Sirven para exteriores?",
             "Solo las que dicen resistentes al agua. Las de interior se dañan con la lluvia."),
        ],
    },
    {
        "category": "hogar", "slug": "humidificadores-y-difusores", "name": "Humidificadores y difusores de aroma",
        "include": ["humidificador", "humificador", "difusor aroma", "difusor de aroma", "difusor aromas",
                    "difusor de aromas", "difusor aceites", "aromatizador", "difusor"],
        "exclude": [],
        "intro": (
            "Los humidificadores y difusores de aroma dispersan una bruma fina de agua, con unas gotas de esencia "
            "si quieres perfumar el espacio. Muchos traen luz de colores y apagado automático cuando se acaba el "
            "agua.\n\n"
            "Para un cuarto basta un modelo de 300 a 500 ml; para la sala, uno de mayor capacidad. Usa esencias "
            "solubles en agua para difusor: los aceites espesos pueden tapar el mecanismo."
        ),
        "faq": [
            ("¿Qué esencias puedo usar?",
             "Esencias o aceites para difusor, solubles en agua, unas pocas gotas por llenado. No uses perfumes ni "
             "aceites de cocina."),
            ("¿Se apaga solo?",
             "La mayoría se apaga cuando el tanque se queda sin agua y algunos tienen temporizador; está indicado "
             "en cada ficha."),
        ],
    },
    {
        "category": "hogar", "slug": "ventiladores", "name": "Ventiladores",
        "include": ["ventilador", "ventiladores", "enfriador de aire", "aire acondicionado portatil", "abanico"],
        "exclude": ["laptop", "portatil gamer", "pc", "computador"],
        "intro": (
            "Ventiladores de mesa, de cuello, de techo, de pedestal y portátiles recargables, más enfriadores de "
            "aire con agua o hielo para los días de más calor.\n\n"
            "Los recargables por USB sirven para la oficina, el carro o cuando se va la luz; los de pedestal mueven "
            "más aire en una habitación. Los enfriadores de agua refrescan mejor en climas secos que en climas "
            "húmedos de costa."
        ),
        "faq": [
            ("¿Un enfriador de aire reemplaza un aire acondicionado?",
             "No: refresca el aire cercano y es mucho más económico, pero no enfría toda la habitación como un aire "
             "acondicionado."),
            ("¿Cuánto dura la batería de un ventilador recargable?",
             "Depende de la velocidad; en la ficha de cada modelo está la autonomía."),
        ],
    },
    {
        "category": "hogar", "slug": "aspiradoras", "name": "Aspiradoras",
        "include": ["aspiradora", "aspiradoras", "aspiradora portatil", "aspiradora inalambrica", "robot aspiradora",
                    "aspiradora de mano", "aspiradora carro", "mini aspiradora"],
        "exclude": [],
        "intro": (
            "Aspiradoras inalámbricas de mano, mini aspiradoras para el carro y el teclado, aspiradoras verticales "
            "y robots que barren solos. Para pelos de mascota, migas y polvo del día a día, una inalámbrica de mano "
            "es lo más práctico.\n\n"
            "Compara potencia de succión, tiempo de batería, tamaño del depósito y si el filtro es lavable. Para "
            "alfombras gruesas conviene una vertical con cepillo motorizado."
        ),
        "faq": [
            ("¿Sirven para pelo de mascota?",
             "Las que traen cepillo giratorio o boquilla para tapizados recogen bien el pelo de sofás y camas."),
            ("¿El filtro se cambia?",
             "En la mayoría se lava con agua y se deja secar. Algunos modelos incluyen un filtro de repuesto."),
        ],
    },
    {
        "category": "hogar", "slug": "tendederos-de-ropa", "name": "Tendederos de ropa",
        "include": ["tendedero", "tendederos", "colgador ropa", "secadora de ropa", "secador de ropa", "cuerda de ropa",
                    "tendedero retractil"],
        "exclude": [],
        "intro": (
            "Tendederos plegables de piso, retráctiles de pared, para balcón y de techo con poleas. En apartamentos "
            "sin patio son la manera de secar la ropa sin ocupar el paso todo el día.\n\n"
            "Revisa los metros de cuerda útil, si se pliega contra la pared y cuánto peso soporta. Los retráctiles "
            "se instalan con tornillos y quedan del tamaño de una caja pequeña cuando no se usan."
        ),
        "faq": [
            ("¿Qué tendedero sirve para un balcón pequeño?",
             "Uno retráctil de pared o uno plegable de piso de alas; ambos se recogen cuando no los usas."),
            ("¿Se instalan sin taladro?",
             "Los de piso no necesitan instalación. Los de pared y techo sí requieren tornillos."),
        ],
    },
    {
        "category": "hogar", "slug": "papel-adhesivo-y-vinilos", "name": "Papel adhesivo y vinilos",
        "include": ["papel adhesivo", "papel vinilo", "vinilo adhesivo", "papel tapiz", "papel de colgadura",
                    "sticker pared", "stickers pared", "lamina adhesiva", "papel contact", "panel 3d", "panel adhesivo"],
        "exclude": [],
        "intro": (
            "Papel adhesivo para renovar mesones, cajones y muebles, papel tapiz, paneles 3D autoadhesivos para "
            "paredes y vinilos decorativos. Es la manera más rápida de cambiar un espacio sin pintar ni hacer obra, "
            "ideal si vives en arriendo.\n\n"
            "Calcula los metros cuadrados que vas a cubrir y compra un poco más por los cortes. La superficie debe "
            "estar limpia, seca y lisa; las burbujas salen con una espátula o una tarjeta."
        ),
        "faq": [
            ("¿Se puede quitar después sin dañar la pared?",
             "En superficies pintadas en buen estado, la mayoría se retira despacio sin dañar. En pintura vieja o "
             "húmeda puede levantarla."),
            ("¿Sirve en la cocina o el baño?",
             "Los vinilos lavables sí, lejos del calor directo de la estufa. Revisa en la ficha si es resistente "
             "al agua."),
        ],
    },
    {
        "category": "hogar", "slug": "almohadas-y-cojines", "name": "Almohadas y cojines",
        "include": ["almohada", "almohadas", "cojin", "cojines", "almohada ortopedica", "almohada cervical",
                    "almohada de viaje", "cojin lumbar", "cojin ortopedico", "almohada embarazo"],
        "exclude": [],
        "intro": (
            "Almohadas cervicales y de espuma viscoelástica, cojines lumbares para la silla, cojines de viaje para "
            "el cuello, almohadas para embarazo y cojines decorativos para la sala.\n\n"
            "Si duermes de lado, busca una almohada más alta; boca arriba, una media; boca abajo, una delgada. Para "
            "quien pasa muchas horas sentado, un cojín lumbar ayuda a mantener mejor la postura."
        ),
        "faq": [
            ("¿Las almohadas de memoria se pueden lavar?",
             "La funda sí; la espuma interior se limpia en seco o con un paño húmedo. Revisa las indicaciones de "
             "cada producto."),
            ("¿Cuál es la diferencia entre almohada cervical y normal?",
             "La cervical tiene forma de onda para apoyar el cuello; la normal es pareja. La elección depende de "
             "cómo duermes."),
        ],
    },

    # ── Belleza ───────────────────────────────────────────────────────────────
    {
        "category": "belleza", "slug": "cepillos-secadores", "name": "Cepillos secadores y alisadores",
        "include": ["cepillo secador", "cepillo alisador", "cepillo electrico", "cepillo de aire", "cepillo voluminizador",
                    "cepillo vapor", "cepillo 3 en 1", "cepillo rotativo", "peine alisador", "peine electrico"],
        "exclude": ["dientes", "dental", "facial", "mascota", "perro", "gato", "limpieza"],
        "intro": (
            "Un cepillo secador seca, alisa y da volumen en un solo paso, sin necesidad de secador y plancha por "
            "separado. Los alisadores eléctricos tipo peine dejan el cabello liso con menos tiempo que una plancha "
            "tradicional.\n\n"
            "Para cabello largo o grueso conviene un cepillo de cabeza ovalada grande y varias temperaturas; para "
            "cabello corto, uno más pequeño. Usa siempre protector térmico y pásalo con el cabello casi seco."
        ),
        "faq": [
            ("¿Reemplaza a la plancha?",
             "Para un liso natural con volumen, sí. Para un liso totalmente plano, la plancha sigue dando mejor "
             "resultado."),
            ("¿Sirve para cabello crespo?",
             "Sí, en temperaturas medias y por mechones delgados. Úsalo con protector térmico."),
        ],
    },
    {
        "category": "belleza", "slug": "planchas-y-rizadoras", "name": "Planchas y rizadoras para el cabello",
        "include": ["plancha cabello", "plancha de cabello", "plancha para cabello", "plancha alisadora", "plancha pelo",
                    "plancha para pelo", "rizadora", "rizador", "onduladora", "pinza rizadora", "tenaza"],
        "exclude": ["ropa", "vapor ropa", "plancha de vapor", "plancha ropa", "parrilla", "asar"],
        "intro": (
            "Planchas alisadoras con placas de cerámica o titanio, rizadoras de varios tamaños y onduladoras para "
            "ondas tipo playa. La diferencia está en la temperatura regulable, el tamaño de las placas y el tiempo "
            "de calentamiento.\n\n"
            "Para cabello fino o teñido, temperaturas bajas; para cabello grueso, más altas. Las placas angostas "
            "sirven también para hacer ondas. Usa protector térmico antes de cada pasada."
        ),
        "faq": [
            ("¿Cerámica o titanio?",
             "La cerámica reparte el calor de forma pareja y es más suave; el titanio calienta más rápido y "
             "conviene para cabello grueso."),
            ("¿Qué tamaño de rizadora elegir?",
             "Los barriles delgados hacen rizos definidos; los gruesos, ondas sueltas."),
        ],
    },
    {
        "category": "belleza", "slug": "secadores-de-pelo", "name": "Secadores de pelo",
        "include": ["secador de pelo", "secador pelo", "secador cabello", "secador de cabello", "secador para cabello",
                    "secador profesional", "secador ionico", "gorro secador"],
        "exclude": ["zapatos", "ropa", "cepillo", "unas"],
        "intro": (
            "Secadores profesionales, iónicos, plegables para viaje y gorros secadores. Un secador con varias "
            "velocidades, aire frío y boquilla concentradora seca más rápido y deja el cabello con menos frizz.\n\n"
            "Compara la potencia en vatios, si trae difusor para crespos y el largo del cable. Los plegables son "
            "livianos para la maleta."
        ),
        "faq": [
            ("¿Para qué sirve el botón de aire frío?",
             "Para fijar el peinado al final y cerrar la cutícula; el cabello queda con más brillo."),
            ("¿Necesito difusor?",
             "Si tienes el cabello ondulado o crespo, el difusor seca sin deshacer los rizos."),
        ],
    },
    {
        "category": "belleza", "slug": "maquinas-de-afeitar-y-patilleras", "name": "Máquinas de afeitar y patilleras",
        "include": ["afeitadora", "maquina afeitar", "maquina de afeitar", "patillera", "maquina patillera",
                    "maquina corte", "maquina de corte", "maquina cortar cabello", "maquina para cortar cabello",
                    "cortadora de cabello", "barbera", "trimmer", "recortadora", "rasuradora"],
        "exclude": ["mascota", "perro", "unas", "pelusa", "motas"],
        "intro": (
            "Patilleras para perfilar, máquinas de corte con guías de varias medidas, afeitadoras rotativas y de "
            "láminas, y recortadoras de nariz y oídos. Para cortarte el pelo en casa necesitas una máquina con "
            "guías; para la barba, una patillera o recortadora.\n\n"
            "Revisa la duración de la batería, cuántas guías incluye y si se puede usar conectada. Limpia las "
            "cuchillas con el cepillo que traen después de cada uso."
        ),
        "faq": [
            ("¿Qué diferencia hay entre patillera y máquina de corte?",
             "La patillera tiene cuchilla en T para perfilar líneas; la máquina de corte trae guías para rebajar "
             "el cabello a una medida."),
            ("¿Sirven para mascotas?",
             "No se recomienda; el pelo de los animales es distinto y hay máquinas específicas para ellos."),
        ],
    },
    {
        "category": "belleza", "slug": "depiladoras", "name": "Depiladoras",
        "include": ["depiladora", "depilador", "depilacion", "removedor de vello", "removedor vello", "ipl",
                    "depiladora facial", "rasuradora femenina"],
        "exclude": [],
        "intro": (
            "Depiladoras eléctricas, removedores de vello facial tipo lápiz, depiladoras de luz pulsada para uso en "
            "casa y rasuradoras femeninas. Cada una funciona distinto: las eléctricas arrancan el vello desde la "
            "raíz, las rasuradoras lo cortan al ras y las de luz pulsada reducen el crecimiento con varias "
            "sesiones.\n\n"
            "Lee en cada ficha para qué zonas sirve y cómo se usa. Prueba primero en una zona pequeña."
        ),
        "faq": [
            ("¿La depiladora de luz pulsada sirve para todo tipo de piel?",
             "Funciona mejor en piel clara con vello oscuro. Revisa la tabla de tonos que trae el producto antes "
             "de usarla."),
            ("¿Duele la depiladora eléctrica?",
             "Puede molestar las primeras veces porque arranca el vello; con el uso la molestia disminuye."),
        ],
    },
    {
        "category": "belleza", "slug": "unas-y-manicure", "name": "Uñas y manicure",
        "include": ["pulidor unas", "pulidor de unas", "lampara unas", "lampara de unas", "lampara uv", "taladro unas",
                    "taladro de unas", "kit unas", "kit de unas", "manicure", "pedicure", "esmalte", "unas acrilicas",
                    "cortaunas"],
        "exclude": [],
        "intro": (
            "Todo para hacerte las uñas en casa: lámparas UV/LED para secar semipermanente, pulidores y taladros "
            "eléctricos para limar, kits de manicure y pedicure, y uñas acrílicas.\n\n"
            "Para esmalte semipermanente necesitas lámpara UV/LED; revisa su potencia y si tiene temporizador. "
            "Los taladros traen varias puntas: empieza con la velocidad baja."
        ),
        "faq": [
            ("¿Qué lámpara necesito para el esmalte semipermanente?",
             "Una lámpara UV/LED de al menos 36 W con temporizador seca bien la mayoría de esmaltes."),
            ("¿El pulidor eléctrico sirve para pies?",
             "Sí, con las puntas indicadas para callosidades. Úsalo en piel seca y a velocidad baja."),
        ],
    },
    {
        "category": "belleza", "slug": "cuidado-facial", "name": "Masajeadores faciales y cuidado de la piel",
        "include": ["masajeador facial", "rodillo facial", "limpiador facial", "cepillo facial", "espatula ultrasonica",
                    "gua sha", "vaporizador facial", "mascarilla led", "limpiador de poros", "extractor de puntos negros",
                    "succionador de puntos negros"],
        "exclude": [],
        "intro": (
            "Rodillos y piedras gua sha, cepillos limpiadores, espátulas ultrasónicas, extractores de puntos negros "
            "y vaporizadores para hacer una rutina de cuidado facial en casa.\n\n"
            "Los cepillos limpiadores y las espátulas se usan con la piel húmeda y un limpiador suave; los rodillos "
            "y el gua sha, con un sérum o aceite para que deslicen. Si tienes la piel sensible, empieza con poca "
            "intensidad."
        ),
        "faq": [
            ("¿Cada cuánto usar el cepillo limpiador?",
             "Una vez al día es suficiente para la mayoría de pieles. En piel sensible, día de por medio."),
            ("¿El extractor de puntos negros deja marcas?",
             "Puede dejar enrojecimiento si se usa en la intensidad máxima o mucho tiempo en un mismo punto. Úsalo "
             "en la intensidad más baja y moviéndolo."),
        ],
    },

    {
        "category": "belleza", "slug": "blanqueamiento-dental", "name": "Blanqueamiento dental",
        "include": ["blanqueador dental", "blanqueador dientes", "blanqueador de dientes", "blanqueadora dental",
                    "pasta dental blanqueadora", "pasta blanqueadora", "blanqueamiento dental", "kit de blanqueamiento",
                    "kit blanqueamiento", "lapiz blanqueador", "dazzling white", "white dazzling",
                    "tiras blanqueadoras"],
        "exclude": ["exprimidor", "dispensador", "porta cepillo"],
        "intro": (
            "Kits de blanqueamiento con luz LED, tiras, lápices blanqueadores y pastas dentales blanqueadoras para "
            "aclarar las manchas del café, el té o el cigarrillo desde la casa.\n\n"
            "Sigue el tiempo de aplicación de cada producto y no lo uses más veces de las indicadas: el exceso "
            "puede dar sensibilidad. Si tienes caries, coronas o encías inflamadas, consulta antes con tu "
            "odontólogo; las coronas y resinas no cambian de color."
        ),
        "faq": [
            ("¿Cuándo se notan los resultados?",
             "Depende del producto y de las manchas; la mayoría indica varios días de uso seguido."),
            ("¿Da sensibilidad?",
             "Algunas personas sienten sensibilidad leve. Si pasa, espacia las aplicaciones o suspende el uso."),
        ],
    },
    {
        "category": "belleza", "slug": "colageno-y-biotina", "name": "Colágeno y biotina",
        "include": ["colageno", "biotina"],
        "exclude": [],
        "intro": (
            "Colágeno hidrolizado en polvo, cápsulas y gomas, biotina y combinaciones con vitamina C, además de "
            "shampoos y mascarillas con colágeno. Son de los suplementos más buscados para el cuidado del cabello, "
            "la piel y las uñas.\n\n"
            "Revisa en cada ficha la presentación, cuántas porciones trae y la forma de tomarlo. Son suplementos "
            "alimenticios: no reemplazan una alimentación balanceada. Si estás embarazada, lactando o tomas "
            "medicamentos, consulta antes con tu médico."
        ),
        "faq": [
            ("¿Cuál es la diferencia entre colágeno y biotina?",
             "El colágeno es una proteína; la biotina es una vitamina del complejo B. Varios productos traen las dos."),
            ("¿Cómo se toma el colágeno en polvo?",
             "Disuelto en agua, jugo o batido, en la medida que indica el empaque."),
        ],
    },
    {
        "category": "belleza", "slug": "organizadores-de-maquillaje", "name": "Organizadores de maquillaje y cosmetiqueras",
        "include": ["organizador de maquillaje", "organizador maquillaje", "organizador de cosmeticos",
                    "organizador cosmeticos", "cosmetiquera"],
        "exclude": [],
        "intro": (
            "Organizadores giratorios de 360° y de acrílico para el tocador, organizadores de pared y "
            "cosmetiqueras de viaje, algunas con espejo y luz LED.\n\n"
            "Para el tocador, cuenta cuántas brochas, labiales y bases tienes y elige uno con compartimientos de "
            "esa altura. Para viajar, las cosmetiqueras impermeables y acolchadas protegen los frascos de vidrio."
        ),
        "faq": [
            ("¿Los giratorios se pueden desarmar?",
             "Muchos se arman por niveles y se ajusta la altura de las bandejas; revisa la ficha de cada modelo."),
            ("¿Cómo se limpian?",
             "Con un paño húmedo y jabón suave. Evita el alcohol en el acrílico porque lo opaca."),
        ],
    },
    {
        "category": "belleza", "slug": "eliminadores-de-verrugas", "name": "Eliminadores de verrugas y lunares",
        "include": ["verruga", "verrugas", "wart remover", "luminiix", "tag recede"],
        "exclude": [],
        "intro": (
            "Cauterizadores portátiles, lápices, sprays y cremas para retirar verrugas comunes, lunares de carne y "
            "pequeñas imperfecciones de la piel en casa.\n\n"
            "Un dermatólogo debe revisar antes cualquier lunar que cambie de color, forma o tamaño, que sangre o "
            "que aparezca de un momento a otro. Los cauterizadores traen varios niveles: empieza por el más bajo y "
            "no los uses cerca de los ojos."
        ),
        "faq": [
            ("¿El cauterizador se carga?",
             "La mayoría se cargan por USB y traen puntas de repuesto."),
            ("¿Deja marca?",
             "Puede quedar una costra pequeña mientras sana. Mantén la zona limpia y no la retires a la fuerza."),
        ],
    },

    # ── Salud y bienestar ─────────────────────────────────────────────────────
    {
        "category": "salud_bienestar", "slug": "masajeadores", "name": "Masajeadores",
        "include": ["masajeador", "masajeadores", "pistola masajeadora", "pistola de masaje", "masajeador cuello",
                    "masajeador espalda", "masajeador pies", "masajeador electrico", "masajeador cervical",
                    "almohada masajeadora", "silla masajeadora", "cojin masajeador"],
        "exclude": ["facial", "cuero cabelludo", "intimo", "vibrador", "mascota", "mascotas", "perro", "gato"],
        "intro": (
            "Pistolas de masaje para después del ejercicio, masajeadores de cuello y hombros, de pies, almohadas y "
            "cojines con calor para la silla o el carro. Ayudan a relajarte al final del día sin salir de la casa.\n\n"
            "Las pistolas traen varios cabezales e intensidades para piernas y espalda; los de cuello en forma de U "
            "se usan sentado o acostado. Empieza con la intensidad más baja y no los uses sobre zonas lesionadas."
        ),
        "faq": [
            ("¿Cuánto tiempo seguido se puede usar?",
             "Sesiones de 10 a 15 minutos por zona. Muchos modelos se apagan solos pasado ese tiempo."),
            ("¿Los que tienen calor se pueden usar en el carro?",
             "Sí, los que traen cable de 12 V. Está indicado en la ficha de cada uno."),
        ],
    },
    {
        "category": "salud_bienestar", "slug": "correctores-de-postura", "name": "Correctores de postura",
        "include": ["corrector postura", "corrector de postura", "corrector postural", "faja postural", "chaleco postural"],
        "exclude": [],
        "intro": (
            "Los correctores de postura recuerdan mantener los hombros hacia atrás mientras trabajas sentado o "
            "caminas. Hay tipo arnés para la espalda alta y tipo chaleco con soporte lumbar.\n\n"
            "La talla importa: mide el contorno del pecho y compáralo con la tabla de cada producto. Úsalo por "
            "ratos al principio, de 20 a 30 minutos, y aumenta el tiempo poco a poco."
        ),
        "faq": [
            ("¿Se nota debajo de la ropa?",
             "Los tipo arnés delgados casi no se notan debajo de una camisa o buzo; los chalecos son más visibles."),
            ("¿Cuántas horas al día se usa?",
             "Al principio ratos cortos y luego más tiempo, sin dormir con él puesto."),
        ],
    },
    {
        "category": "salud_bienestar", "slug": "tensiometros-y-medidores", "name": "Tensiómetros, oxímetros y medidores",
        "include": ["tensiometro", "oximetro", "termometro", "glucometro", "bascula", "bascula digital", "pesa digital",
                    "balanza digital", "medidor de presion"],
        "exclude": ["cocina", "equipaje", "maleta", "joyeria", "gramera"],
        "intro": (
            "Tensiómetros de brazo y de muñeca, oxímetros de dedo, termómetros digitales e infrarrojos y básculas "
            "de baño para llevar control en casa.\n\n"
            "Los tensiómetros de brazo suelen dar lecturas más estables que los de muñeca; revisa la talla del "
            "brazalete. Estos equipos son de uso doméstico: ante cualquier valor que te preocupe, consulta a tu "
            "médico."
        ),
        "faq": [
            ("¿Tensiómetro de brazo o de muñeca?",
             "El de brazo es más fácil de usar bien; el de muñeca es más portátil pero exige mantener la muñeca a "
             "la altura del corazón."),
            ("¿Qué pilas usan?",
             "La mayoría usa pilas AA o AAA; algunos son recargables por USB. Está en cada ficha."),
        ],
    },

    {
        "category": "salud_bienestar", "slug": "antihongos", "name": "Tratamientos antihongos para uñas y pies",
        "include": ["antihongos", "anti hongos", "anti hongo", "hongos en unas", "hongos de unas", "hongos unas",
                    "eliminador de hongos", "para hongos", "herbcure", "herbacure", "toenail", "toenailplus",
                    "fungikill", "antimicotico"],
        "exclude": [],
        "intro": (
            "Lociones, sprays, parches, lápices y láser de luz para el cuidado de las uñas de los pies y las manos "
            "afectadas por hongos.\n\n"
            "La constancia es lo que más cuenta: la uña tarda meses en crecer de nuevo, así que hay que aplicar el "
            "producto todos los días durante el tiempo que indica el fabricante. Mantén los pies secos, cambia las "
            "medias a diario y no compartas cortaúñas. Si la infección se extiende o hay dolor, consulta a un médico."
        ),
        "faq": [
            ("¿Cuánto tiempo hay que usarlo?",
             "Varias semanas o meses, según el producto; sigue la indicación del empaque sin suspenderlo antes."),
            ("¿Sirve el láser de luz?",
             "Se usa como complemento del cuidado diario, en sesiones cortas según su manual."),
        ],
    },
    {
        "category": "salud_bienestar", "slug": "cremas-para-dolores-musculares", "name": "Cremas y geles para dolores musculares",
        "include": ["crema dolores", "crema para dolores", "crema para el dolor", "crema dolor", "dolores musculares",
                    "dolor muscular", "dolores y articulaciones", "articulaciones", "arnica", "diclofenaco", "circuvena",
                    "beevana", "clear zal", "gel caliente", "perfectx"],
        "exclude": ["rodillera", "almohada", "faja", "bolsa", "gorro", "manta", "cojin", "tobillera", "munequera",
                    "plantilla", "masajeador", "cinturon", "parche", "parches", "electrodo", "electrodos", "compresa",
                    "venda", "colageno", "fortalecedor"],
        "intro": (
            "Cremas, geles y ungüentos de uso externo para aplicar con masaje en espalda, cuello, rodillas y "
            "piernas después del trabajo, el ejercicio o un esfuerzo: fórmulas con árnica, efecto frío o calor y "
            "marcas muy buscadas como Perfectx, Beevana y Clear Zal.\n\n"
            "Aplícalas sobre piel sana, sin heridas, y lávate las manos después. Si el dolor es fuerte, viene de un "
            "golpe o no mejora en unos días, consulta con un médico."
        ),
        "faq": [
            ("¿Cada cuánto se aplica?",
             "Normalmente de 2 a 3 veces al día con un masaje suave; revisa la indicación de cada producto."),
            ("¿Se pueden usar antes de hacer ejercicio?",
             "Las de efecto calor se usan antes para calentar; las de efecto frío, después."),
        ],
    },

    # ── Moda y accesorios ─────────────────────────────────────────────────────
    {
        "category": "moda_accesorios", "slug": "fajas-y-moldeadores", "name": "Fajas y moldeadores",
        "include": ["faja", "fajas", "moldeador", "moldeadora", "short moldeador", "cinturilla", "body moldeador",
                    "levanta cola", "levantacola"],
        "exclude": ["postural", "lumbar deportiva"],
        "intro": (
            "Fajas, cinturillas, shorts y bodys moldeadores para usar debajo de la ropa. La compresión cambia "
            "según el modelo: las cinturillas se enfocan en el abdomen y los shorts moldean también la cadera.\n\n"
            "Elige la talla con la tabla de medidas de cada producto y no por la talla de ropa que usas; una talla "
            "muy pequeña incomoda y se enrolla. Si quedas entre dos tallas, escríbenos y te orientamos."
        ),
        "faq": [
            ("¿Cómo sé mi talla?",
             "Mide cintura y cadera con un metro de costura y compáralas con la tabla de la ficha del producto."),
            ("¿Se pueden usar todo el día?",
             "Depende de la compresión. Empieza con pocas horas y aumenta si te sientes cómoda."),
        ],
    },
    {
        "category": "moda_accesorios", "slug": "maletas-y-morrales", "name": "Maletas y morrales",
        "include": ["maleta", "maletas", "morral", "morrales", "mochila", "maletin", "bolso de viaje", "maleta de viaje",
                    "rinonera"],
        "exclude": ["herramientas", "maquillaje", "cosmetiquera", "arte", "llavero", "bebe", "arnes", "portabebe",
                    "juguete", "nina", "nino"],
        "intro": (
            "Maletas de viaje rígidas, morrales para el portátil, morrales antirrobo, maletines de mano y canguros. "
            "Para viajar en avión, revisa las medidas permitidas por la aerolínea para equipaje de mano.\n\n"
            "En los morrales para portátil, mira el tamaño de pantalla que cabe en el bolsillo acolchado; los "
            "antirrobo tienen cremalleras ocultas y puerto USB para cargar el celular."
        ),
        "faq": [
            ("¿La maleta sirve como equipaje de mano?",
             "Las de 20 pulgadas suelen cumplir con la mayoría de aerolíneas, pero revisa la medida exacta de tu "
             "aerolínea con las de la ficha."),
            ("¿El puerto USB del morral trae batería?",
             "No; es un paso de cable. Conectas por dentro tu batería portátil y cargas el celular por fuera."),
        ],
    },
    {
        "category": "moda_accesorios", "slug": "gafas-de-sol", "name": "Gafas",
        "include": ["gafas", "gafas de sol", "lentes de sol", "gafas polarizadas", "gafas filtro azul", "gafas luz azul"],
        "exclude": ["realidad virtual", "vr", "natacion", "3d", "soldar", "seguridad industrial"],
        "intro": (
            "Gafas de sol, polarizadas para manejar y estar al aire libre, y gafas con filtro de luz azul para "
            "pasar muchas horas frente a la pantalla.\n\n"
            "Las polarizadas reducen los reflejos del pavimento y del agua; para manejar son las más cómodas. Las "
            "de filtro azul no tienen fórmula y sirven para trabajar en el computador o el celular."
        ),
        "faq": [
            ("¿Qué diferencia hay entre gafas polarizadas y oscuras normales?",
             "Las polarizadas eliminan el reflejo de superficies brillantes; las oscuras solo reducen la cantidad "
             "de luz."),
            ("¿Las de filtro azul tienen aumento?",
             "No, son lentes sin fórmula. Si usas gafas formuladas, consulta con tu óptica."),
        ],
    },

    # ── Deporte y fitness ─────────────────────────────────────────────────────
    {
        "category": "deporte_fitness", "slug": "ejercicio-en-casa", "name": "Ejercicio en casa",
        "include": ["bandas elasticas", "banda elastica", "bandas de resistencia", "banda de resistencia", "rueda abdominal",
                    "tabla push", "tabla de flexiones", "barra dominadas", "barra de dominadas", "ejercitador",
                    "mancuerna", "mancuernas", "pesas gimnasio", "pesas tobilleras", "lazo", "cuerda para saltar", "colchoneta", "mat de yoga",
                    "tapete yoga", "gimnasia pasiva"],
        "exclude": ["cepillo", "secador"],
        "intro": (
            "Lo necesario para entrenar sin gimnasio: bandas elásticas de varias resistencias, rueda abdominal, "
            "tabla de flexiones, barra para la puerta, mancuernas, lazos y colchonetas.\n\n"
            "Si estás empezando, un set de bandas elásticas y una colchoneta permiten trabajar todo el cuerpo con "
            "poco espacio. La barra para puerta necesita un marco firme: revisa el rango de ancho que admite."
        ),
        "faq": [
            ("¿Qué resistencia de bandas elegir?",
             "Los sets traen varias. Empieza con la más liviana para aprender el movimiento y sube cuando hagas "
             "las repeticiones con facilidad."),
            ("¿La barra de dominadas daña el marco de la puerta?",
             "Las de presión traen protectores de goma. Instálala en marcos firmes y revisa el ancho admitido."),
        ],
    },
    {
        "category": "deporte_fitness", "slug": "rodilleras-y-soportes", "name": "Rodilleras y soportes deportivos",
        "include": ["rodillera", "rodilleras", "tobillera", "tobilleras", "munequera", "munequeras", "codera", "coderas",
                    "soporte lumbar", "cinturon lumbar", "faja deportiva", "guantes gimnasio", "guantes de gimnasio"],
        "exclude": [],
        "intro": (
            "Rodilleras, tobilleras, muñequeras, coderas y cinturones lumbares para entrenar, correr o trabajar con "
            "más soporte, y guantes para levantar pesas sin callos.\n\n"
            "La talla se toma con la medida de la articulación (contorno de la rodilla o del tobillo), según la "
            "tabla de cada producto. Son un apoyo; si tienes una lesión, consulta a un profesional."
        ),
        "faq": [
            ("¿Cómo sé la talla de la rodillera?",
             "Mide el contorno de la rodilla un poco arriba de la rótula, con la pierna estirada, y compáralo con la "
             "tabla."),
            ("¿Se pueden lavar?",
             "Sí, a mano con agua fría y jabón suave, secándolas a la sombra."),
        ],
    },

    # ── Tecnología ────────────────────────────────────────────────────────────
    {
        "category": "tecnologia", "slug": "audifonos-inalambricos", "name": "Audífonos inalámbricos",
        "include": ["audifonos", "audifono", "audifonos inalambricos", "audifonos bluetooth", "diadema", "diademas",
                    "manos libres", "auriculares"],
        "exclude": ["cable aux", "adaptador", "estuche", "forro", "case", "funda"],
        "intro": (
            "Audífonos inalámbricos de botón con estuche de carga, diademas bluetooth, audífonos deportivos con "
            "gancho y diademas gamer con micrófono.\n\n"
            "Compara la duración de la batería con el estuche, la versión de bluetooth y si tienen micrófono para "
            "llamadas. Para hacer deporte, los de gancho o de conducción ósea no se caen al correr."
        ),
        "faq": [
            ("¿Funcionan con cualquier celular?",
             "Sí, con Android y iPhone por bluetooth. Algunas funciones táctiles pueden variar según el teléfono."),
            ("¿Cuánto dura la batería?",
             "Cada ficha indica las horas de uso por carga y las cargas adicionales que da el estuche."),
        ],
    },
    {
        "category": "tecnologia", "slug": "parlantes-bluetooth", "name": "Parlantes bluetooth",
        "include": ["parlante", "parlantes", "bafle", "cabina de sonido", "torre de sonido", "altavoz", "barra de sonido"],
        "exclude": [],
        "intro": (
            "Parlantes bluetooth portátiles, resistentes al agua para la piscina, bafles con micrófono para "
            "karaoke y barras de sonido para el televisor.\n\n"
            "Para llevar a paseos busca batería de varias horas y resistencia al agua; para fiestas en casa, un "
            "bafle con micrófono y luces. Revisa también si trae radio, entrada USB o memoria."
        ),
        "faq": [
            ("¿Se pueden conectar dos parlantes juntos?",
             "Algunos modelos tienen función TWS para emparejar dos iguales; si es así, está en la ficha."),
            ("¿Sirven para karaoke?",
             "Los que incluyen micrófono o entrada para micrófono sí. Revisa qué trae la caja."),
        ],
    },
    {
        "category": "tecnologia", "slug": "relojes-inteligentes", "name": "Relojes inteligentes",
        "include": ["smart watch", "smartwatch", "reloj inteligente", "reloj smart", "manilla inteligente", "smart band",
                    "smartband", "reloj deportivo inteligente"],
        "exclude": ["pulso", "correa", "protector", "cargador"],
        "intro": (
            "Relojes inteligentes y manillas que muestran las notificaciones del celular, cuentan pasos, miden el "
            "sueño y, en muchos modelos, permiten contestar llamadas desde la muñeca.\n\n"
            "Revisa la compatibilidad con tu celular, la duración de la batería y si es resistente al agua para "
            "lavarte las manos o nadar. Los datos de salud son orientativos, no reemplazan equipos médicos."
        ),
        "faq": [
            ("¿Funciona con iPhone?",
             "La mayoría funciona con Android y iPhone a través de su aplicación; está indicado en cada ficha."),
            ("¿Se puede contestar llamadas?",
             "Solo los modelos con micrófono y parlante. Revisa que la ficha mencione llamadas por bluetooth."),
        ],
    },
    {
        "category": "tecnologia", "slug": "proyectores", "name": "Proyectores",
        "include": ["proyector", "proyectores", "mini proyector", "video beam", "videobeam"],
        "exclude": ["galaxia", "estrellas", "luces", "aurora", "luna", "astronauta", "lampara"],
        "intro": (
            "Mini proyectores para ver películas y series en la pared del cuarto, proyectores con sistema "
            "integrado para conectarse al wifi y video beams para presentaciones.\n\n"
            "La resolución nativa y los lúmenes definen qué tan nítida y brillante se ve la imagen: para ver de "
            "noche en un cuarto oscuro basta un mini proyector; con luz ambiente se necesitan más lúmenes. Revisa "
            "las entradas (HDMI, USB) y si trae parlante."
        ),
        "faq": [
            ("¿Se puede conectar el celular?",
             "Sí, por cable o por duplicación de pantalla en los modelos con wifi. La ficha indica cómo."),
            ("¿Se ve de día?",
             "Los mini proyectores se ven bien en ambientes oscuros. Con luz del día la imagen pierde brillo."),
        ],
    },
    {
        "category": "tecnologia", "slug": "consolas-retro", "name": "Consolas de videojuegos retro",
        "include": ["consola", "consolas", "consola retro", "consola portatil", "game stick", "gamestick", "game box",
                    "gamebox", "control gamer", "control inalambrico"],
        "exclude": [],
        "intro": (
            "Consolas portátiles y game sticks que se conectan al televisor con miles de juegos clásicos ya "
            "cargados, más controles inalámbricos para jugar de a dos.\n\n"
            "Compara el tamaño de pantalla en las portátiles, cuántos controles incluye el game stick y la memoria "
            "que trae. Son ideales para revivir los juegos de antes o como regalo."
        ),
        "faq": [
            ("¿Se necesita internet para jugar?",
             "No, los juegos vienen cargados en la memoria."),
            ("¿Cómo se conecta al televisor?",
             "Por HDMI. Si tu televisor es antiguo y no tiene esa entrada, pregúntanos antes de comprar."),
        ],
    },
    {
        "category": "tecnologia", "slug": "soportes-para-celular", "name": "Soportes para celular",
        "include": ["soporte celular", "soporte de celular", "soporte para celular", "soporte magnetico", "holder",
                    "soporte para carro", "soporte moto celular", "soporte tablet", "tripode celular", "selfie stick",
                    "palo selfie", "estabilizador"],
        "exclude": [],
        "intro": (
            "Soportes de celular para el carro, la moto, el escritorio y la cama, trípodes, palos selfie y "
            "estabilizadores para grabar videos sin que se muevan.\n\n"
            "Para el carro, revisa si se pega al tablero, va en la rejilla del aire o es magnético. Para la moto "
            "busca agarre firme al manubrio. Para grabar contenido, un trípode con control remoto bluetooth."
        ),
        "faq": [
            ("¿El soporte magnético sirve con forro?",
             "Con forros delgados sí; con forros gruesos o de billetera pierde fuerza. Algunos traen una placa "
             "metálica para pegar."),
            ("¿El soporte para moto aguanta huecos?",
             "Los de abrazadera con seguro están hechos para eso. Ajústalo bien y revisa que el celular quede "
             "trabado."),
        ],
    },
    {
        "category": "tecnologia", "slug": "cargadores-y-baterias", "name": "Cargadores, cables y baterías portátiles",
        "include": ["cargador", "cargadores", "cable usb", "cable tipo c", "cable lightning", "cable de carga",
                    "power bank", "powerbank", "bateria portatil", "bateria externa", "cargador inalambrico",
                    "cargador carro", "cargador de carro"],
        "exclude": ["pilas", "taladro", "herramienta", "bateria para carro", "bebe", "fular", "fullar", "portabebe", "ergonomico"],
        "intro": (
            "Cargadores rápidos de pared y de carro, cables tipo C, micro USB y para iPhone, cargadores "
            "inalámbricos y baterías portátiles para no quedarte sin celular en la calle.\n\n"
            "En las baterías portátiles, la capacidad en mAh dice cuántas cargas te da: 10.000 mAh alcanza para dos "
            "cargas de un celular promedio. Revisa que el conector coincida con tu teléfono."
        ),
        "faq": [
            ("¿El cargador rápido sirve para mi celular?",
             "Si tu celular admite carga rápida, sí aprovecha la velocidad; si no, carga a la velocidad normal sin "
             "dañarlo."),
            ("¿Puedo llevar la batería portátil en el avión?",
             "Sí, en el equipaje de mano. Las de hasta 20.000 mAh están dentro de lo permitido por la mayoría de "
             "aerolíneas."),
        ],
    },
    {
        "category": "tecnologia", "slug": "aros-de-luz-y-microfonos", "name": "Aros de luz y micrófonos",
        "include": ["aro luz", "aro de luz", "anillo de luz", "ring light", "microfono", "microfonos", "microfono inalambrico",
                    "microfono solapa", "kit youtuber", "kit creador"],
        "exclude": ["muneco", "muneca", "bebe", "juguete", "infantil"],
        "intro": (
            "Aros de luz con trípode, micrófonos de solapa inalámbricos y kits para crear contenido, hacer clases "
            "virtuales o vender en vivo con buena imagen y sonido.\n\n"
            "Para grabar con el celular, un aro de 10 a 18 pulgadas con trípode alto ilumina bien la cara; un "
            "micrófono de solapa inalámbrico mejora mucho el audio en exteriores. Revisa el conector del micrófono "
            "(tipo C o iPhone)."
        ),
        "faq": [
            ("¿El micrófono inalámbrico sirve con mi celular?",
             "Hay versiones con conector tipo C y para iPhone; revisa cuál corresponde al tuyo en la ficha."),
            ("¿Qué tamaño de aro de luz elegir?",
             "Para el celular y la cara, de 10 a 12 pulgadas; para cuerpo entero o productos, de 18 pulgadas."),
        ],
    },

    # ── Seguridad ─────────────────────────────────────────────────────────────
    {
        "category": "seguridad", "slug": "camaras-de-seguridad", "name": "Cámaras de seguridad",
        "include": ["camara seguridad", "camara de seguridad", "camara wifi", "camara ip", "camara bombillo",
                    "camara bombilla", "camara solar", "camara exterior", "camara 360", "camara robotica",
                    "camara vigilancia", "camara de vigilancia", "timbre camara", "timbre inteligente"],
        "exclude": ["celular", "selfie", "infantil", "deportiva", "accion", "instantanea"],
        "intro": (
            "Cámaras wifi que ves desde el celular: tipo bombillo que se enroscan en un plafón, robóticas que giran "
            "360°, de exterior resistentes a la lluvia, solares con chip para fincas sin internet y timbres con "
            "cámara.\n\n"
            "Revisa si necesita wifi o funciona con SIM, si graba en memoria micro SD o en la nube, la visión "
            "nocturna y si tiene audio de dos vías. Las de exterior deben decir resistencia al agua (IP65 o "
            "superior)."
        ),
        "faq": [
            ("¿La cámara funciona sin internet?",
             "Las wifi necesitan red para verla desde el celular; muchas graban igual en la memoria. Las de SIM "
             "usan datos móviles, útiles para fincas o lotes."),
            ("¿La memoria viene incluida?",
             "No siempre. En la ficha está si trae micro SD y la capacidad máxima que admite."),
        ],
    },
    {
        "category": "seguridad", "slug": "candados-y-cerraduras", "name": "Candados, cerraduras y alarmas",
        "include": ["candado", "candados", "cerradura", "cerraduras", "chapa digital", "chapa inteligente", "alarma",
                    "alarmas", "sensor de movimiento", "sensor puerta", "caja fuerte"],
        "exclude": ["reloj", "despertador", "carro alarma", "alcancia"],
        "intro": (
            "Candados con alarma para motos y bicicletas, cerraduras digitales con huella o clave, alarmas para "
            "puertas y ventanas, sensores de movimiento y cajas fuertes pequeñas.\n\n"
            "Para una cerradura digital mide el grosor de la puerta y revisa cómo se abre si se descarga la "
            "batería. Los sensores con alarma de puerta se pegan sin herramientas."
        ),
        "faq": [
            ("¿Qué pasa si se descarga la chapa digital?",
             "Casi todas traen llave mecánica de emergencia o un puerto para cargarla por fuera. Revisa la ficha "
             "del modelo."),
            ("¿El candado con alarma suena fuerte?",
             "Sí, la mayoría pasa de 100 decibeles al moverlo, lo suficiente para disuadir."),
        ],
    },

    # ── Herramientas ──────────────────────────────────────────────────────────
    {
        "category": "herramientas", "slug": "taladros-y-atornilladores", "name": "Taladros y atornilladores",
        "include": ["taladro", "taladros", "atornillador", "destornillador electrico", "rotomartillo", "pulidora",
                    "amoladora", "sierra electrica", "caladora"],
        "exclude": ["unas", "dental"],
        "intro": (
            "Taladros inalámbricos y percutores, atornilladores, rotomartillos para concreto, pulidoras y sierras "
            "para trabajos en casa o en obra.\n\n"
            "Para colgar cuadros y armar muebles, un taladro inalámbrico de 12 a 21 V es suficiente. Para perforar "
            "concreto, uno con percusión o un rotomartillo. Revisa cuántas baterías incluye y si trae brocas."
        ),
        "faq": [
            ("¿Un taladro inalámbrico perfora concreto?",
             "Solo si tiene función de percusión y con broca para concreto. Para trabajos frecuentes en concreto "
             "conviene un rotomartillo."),
            ("¿Trae baterías?",
             "En la ficha de cada uno está cuántas baterías y qué accesorios incluye."),
        ],
    },
    {
        "category": "herramientas", "slug": "hidrolavadoras-y-compresores", "name": "Hidrolavadoras y compresores",
        "include": ["hidrolavadora", "hidrolavadoras", "pistola de agua a presion", "lavadora a presion",
                    "compresor", "compresores", "compresor de aire", "inflador", "infladores"],
        "exclude": ["colchon"],
        "intro": (
            "Hidrolavadoras para lavar el carro, la moto, pisos y fachadas, y compresores e infladores portátiles "
            "para llantas, balones y colchones.\n\n"
            "Las hidrolavadoras inalámbricas se conectan a un balde o manguera y son prácticas en conjuntos sin "
            "toma de agua cerca. Los infladores portátiles se conectan al carro o se cargan por USB y muestran la "
            "presión en pantalla."
        ),
        "faq": [
            ("¿La hidrolavadora necesita toma de agua?",
             "Las inalámbricas pueden tomar agua de un balde con la manguera de succión. Las eléctricas grandes "
             "van conectadas a la llave."),
            ("¿El inflador sirve para llantas de carro?",
             "Sí, los que indican la presión máxima suficiente y conexión de 12 V o batería."),
        ],
    },
    {
        "category": "herramientas", "slug": "juegos-de-herramientas", "name": "Juegos de herramientas",
        "include": ["juego herramientas", "juego de herramientas", "set herramientas", "set de herramientas",
                    "kit herramientas", "kit de herramientas", "caja herramientas", "caja de herramientas",
                    "juego de llaves", "juego llaves", "juego de copas", "juego copas", "juego destornilladores",
                    "set destornilladores", "set de destornilladores"],
        "exclude": [],
        "intro": (
            "Juegos de llaves y copas, destornilladores con puntas intercambiables y cajas completas para tener a "
            "mano lo necesario en la casa, el carro o el taller.\n\n"
            "Compara el número de piezas y, sobre todo, cuáles son: para la casa basta un set con destornilladores, "
            "alicate, martillo y metro; para el carro o la moto, un juego de copas con ratchet."
        ),
        "faq": [
            ("¿Qué juego sirve para el carro?",
             "Uno de copas con ratchet en medidas métricas y algunas llaves combinadas."),
            ("¿Viene con estuche?",
             "La mayoría sí. Está indicado en cada producto."),
        ],
    },

    # ── Juguetes, bebés y mascotas ────────────────────────────────────────────
    {
        "category": "juguetes", "slug": "juegos-de-mesa", "name": "Juegos de mesa",
        "include": ["juego mesa", "juego de mesa", "juegos de mesa", "domino", "ajedrez", "jenga", "rompecabezas",
                    "juego de cartas", "naipes", "baraja", "loteria", "monopolio", "juego de memoria"],
        "exclude": ["tarot", "resma", "hojas", "corral", "bebe"],
        "intro": (
            "Juegos de mesa para la familia y los amigos: dominó, ajedrez, parqués, rompecabezas, juegos de cartas, "
            "torres de bloques y juegos de memoria para niños.\n\n"
            "En cada ficha está el número de jugadores y la edad recomendada. Son un buen regalo para reuniones y "
            "para desconectarse de las pantallas."
        ),
        "faq": [
            ("¿Para qué edades son?",
             "Cada juego indica la edad recomendada; los de piezas pequeñas no son para menores de 3 años."),
            ("¿Cuántas personas pueden jugar?",
             "Está en la ficha de cada juego, junto con lo que trae la caja."),
        ],
    },
    {
        "category": "juguetes", "slug": "carros-y-juguetes-a-control-remoto", "name": "Carros y juguetes a control remoto",
        "include": ["carro control remoto", "carro a control", "carro rc", "control remoto carro", "dron", "drones",
                    "pista de carros", "pista carros", "helicoptero control", "montable", "carro montable"],
        "exclude": [],
        "intro": (
            "Carros a control remoto todoterreno, pistas armables, drones para principiantes, helicópteros y "
            "montables para niños.\n\n"
            "Revisa la edad recomendada, el tipo de batería y cuánto dura la carga. Para empezar con drones, uno "
            "con altura fija y botón de despegue automático es más fácil de manejar."
        ),
        "faq": [
            ("¿Trae baterías?",
             "Muchos incluyen batería recargable para el carro; el control puede necesitar pilas aparte. Está en "
             "la ficha."),
            ("¿Sirve en exteriores?",
             "Los todoterreno sí; los de pista son para interior."),
        ],
    },
    {
        "category": "juguetes", "slug": "juguetes-didacticos", "name": "Juguetes didácticos",
        "include": ["didactico", "didactica", "didacticos", "montessori", "bloques", "fichas magneticas", "tablero magico",
                    "tablero de dibujo", "pizarra magica", "juguete educativo", "aprendizaje", "ensartado"],
        "exclude": [],
        "intro": (
            "Juguetes que enseñan mientras juegan: bloques y fichas magnéticas para construir, tableros de dibujo "
            "LCD, materiales Montessori, ensartados y juegos para aprender números, letras y colores.\n\n"
            "Elige según la edad: los primeros años, piezas grandes y texturas; desde los 3 años, construcción y "
            "encaje; más adelante, retos de lógica. La edad recomendada está en cada ficha."
        ),
        "faq": [
            ("¿Las fichas magnéticas son seguras para niños pequeños?",
             "Revisa la edad recomendada: las piezas pequeñas no son para menores de 3 años."),
            ("¿El tablero LCD necesita pilas?",
             "Usa una pila de botón que dura mucho tiempo; muchos la traen incluida."),
        ],
    },
    {
        "category": "bebes", "slug": "lactancia-y-alimentacion", "name": "Lactancia y alimentación del bebé",
        "include": ["extractor de leche", "extractor leche", "sacaleches", "biberon", "tetero", "teteros",
                    "esterilizador", "calentador de teteros", "babero", "lactancia", "cojin lactancia"],
        "exclude": ["disfraz", "dientes", "cepillos"],
        "intro": (
            "Extractores de leche eléctricos y manuales, teteros, esterilizadores, calentadores, baberos y cojines "
            "de lactancia para los primeros meses.\n\n"
            "Los extractores eléctricos dobles ahorran tiempo si te extraes varias veces al día; los manuales son "
            "silenciosos y fáciles de llevar. Revisa el tamaño de la copa y qué piezas trae de repuesto."
        ),
        "faq": [
            ("¿Extractor eléctrico o manual?",
             "El eléctrico es más rápido y cómodo para uso diario; el manual sirve para ocasiones puntuales o "
             "viajes."),
            ("¿Cómo se esterilizan las piezas?",
             "Hirviéndolas o con esterilizador, siguiendo las indicaciones del producto. El motor nunca se moja."),
        ],
    },
    {
        "category": "mascotas", "slug": "productos-para-perros", "name": "Productos para perros",
        "include": ["perro", "perros", "canino", "collar perro", "pechera", "correa perro", "cama perro", "comedero",
                    "bebedero", "juguete perro", "cepillo mascota", "guante quitapelo"],
        "exclude": ["gato"],
        "intro": (
            "Camas, pecheras y correas, comederos y bebederos automáticos, juguetes resistentes y cepillos "
            "quitapelo para el cuidado diario de tu perro.\n\n"
            "Para pecheras y collares, mide el contorno del cuello y del pecho detrás de las patas delanteras. Las "
            "camas se eligen por el largo del perro dormido estirado, con unos centímetros de más."
        ),
        "faq": [
            ("¿Cómo elijo la talla de la pechera?",
             "Mide el contorno del pecho detrás de las patas delanteras y compáralo con la tabla del producto."),
            ("¿El bebedero automático necesita electricidad?",
             "Las fuentes con filtro sí; los dispensadores por gravedad no."),
        ],
    },
    {
        "category": "mascotas", "slug": "productos-para-gatos", "name": "Productos para gatos",
        "include": ["gato", "gatos", "felino", "rascador", "arenero", "arena gato", "juguete gato", "cama gato",
                    "fuente gato", "tunel gato"],
        "exclude": ["perro"],
        "intro": (
            "Rascadores, areneros, fuentes de agua, camas, túneles y juguetes interactivos para que tu gato se "
            "entretenga y no rasguñe los muebles.\n\n"
            "Un rascador estable y alto se usa más que uno pequeño. Muchos gatos toman más agua en una fuente con "
            "movimiento que en un plato quieto."
        ),
        "faq": [
            ("¿Cómo hago que use el rascador?",
             "Ponlo cerca de donde ya rasguña y frótale un poco de catnip. Recompénsalo cuando lo use."),
            ("¿La fuente hace ruido?",
             "Las de bomba sumergida son silenciosas; cambia el filtro según indique el producto."),
        ],
    },

    # ── Vehículos ─────────────────────────────────────────────────────────────
    {
        "category": "vehiculos", "slug": "accesorios-para-moto", "name": "Accesorios para moto",
        "include": ["intercomunicador", "intercomunicadores", "moto", "motos", "casco", "guantes moto", "impermeable moto",
                    "exploradoras", "par exploradoras", "luces moto", "alarma moto"],
        "exclude": ["juguete", "montable", "control remoto"],
        "intro": (
            "Intercomunicadores bluetooth para el casco, exploradoras LED, soportes para celular, impermeables, "
            "guantes y alarmas para moto.\n\n"
            "Los intercomunicadores permiten contestar llamadas, oír el GPS y hablar con el parrillero; revisa el "
            "alcance y si son resistentes al agua. Las exploradoras requieren conexión a la batería de la moto."
        ),
        "faq": [
            ("¿El intercomunicador sirve con cualquier casco?",
             "Sí, se fija con soporte de pinza o adhesivo. Los parlantes van dentro del casco."),
            ("¿Las exploradoras se instalan solas?",
             "Se conectan a la batería de la moto; si no tienes experiencia, es mejor que las instale un técnico."),
        ],
    },
    {
        "category": "vehiculos", "slug": "accesorios-para-carro", "name": "Accesorios para carro",
        "include": ["para carro", "de carro", "del carro", "para el carro", "para auto", "para vehiculo", "carro nuevo",
                    "aspiradora carro", "cargador carro", "soporte carro", "organizador carro", "camara reversa",
                    "sensor reversa", "funda timon", "cubre timon", "parasol", "ambientador carro", "porta celular carro"],
        "exclude": ["control remoto", "juguete", "montable", "carro de mercado", "pista", "transformer", "armable",
                    "friccion", "nascar", "didactico", "carrito", "lanzador"],
        "intro": (
            "Organizadores para el baúl y el asiento, aspiradoras para el carro, cámaras y sensores de reversa, "
            "parasoles, fundas para el timón, soportes para el celular y ambientadores.\n\n"
            "Las cámaras de reversa con pantalla se instalan sin cambiar el radio; las de conexión a la pantalla "
            "original dependen del modelo del carro. Revisa medidas en organizadores y parasoles."
        ),
        "faq": [
            ("¿La cámara de reversa sirve para mi carro?",
             "Las que traen su propia pantalla sirven para cualquier carro. Si quieres verla en la pantalla del "
             "radio, escríbenos con la marca y el modelo."),
            ("¿El parasol se ajusta a cualquier parabrisas?",
             "Revisa las medidas del producto contra el ancho de tu parabrisas antes de pedir."),
        ],
    },
]
