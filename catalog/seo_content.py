"""Textos SEO por categoría (clave = Category.dropi_id sin "store:").

`description` va a la meta description (≤155 caracteres) y `intro` se muestra
bajo el H1 de la categoría: contenido propio y con las búsquedas reales de la
categoría, en vez de una página que solo lista productos.
"""

CATEGORY_SEO = {
    "belleza": {
        "description": "Productos de belleza, maquillaje, skincare y cuidado capilar con pago contra entrega. Envío a todo México.",
        "intro": "Maquillaje, sérums, cremas, cuidado del cabello y accesorios de belleza para tu rutina diaria. Pagas cuando recibes el pedido en tu casa, en cualquier parte de México.",
    },
    "tecnologia": {
        "description": "Tecnología con pago contra entrega: audífonos, bocinas, cargadores, smartwatch y accesorios. Envío a todo México.",
        "intro": "Audífonos, bocinas bluetooth, cargadores, relojes inteligentes, cámaras y accesorios para celular y computadora. Revisas tu pedido y pagas al recibirlo.",
    },
    "salud_bienestar": {
        "description": "Productos de salud y bienestar con pago contra entrega: cuidado personal, masajeadores y más. Envío a todo México.",
        "intro": "Masajeadores, cuidado personal, ortopedia y productos para sentirte mejor cada día. Compra sin pagar por adelantado: pagas al recibir en tu casa.",
    },
    "bienestar_intimo": {
        "description": "Bienestar íntimo con envío discreto y pago contra entrega. Productos para el cuidado y el placer en pareja, enviados a todo México.",
        "intro": "Productos de cuidado íntimo y bienestar en pareja con empaque discreto. Pagas contra entrega y recibes en cualquier parte de México.",
    },
    "hogar": {
        "description": "Artículos para el hogar con pago contra entrega: organización, decoración, limpieza y más. Envío a todo México.",
        "intro": "Organizadores, decoración, iluminación, limpieza y soluciones prácticas para cada espacio de tu casa. Pagas cuando el pedido llega a tu puerta.",
    },
    "cocina": {
        "description": "Utensilios y electrodomésticos de cocina con pago contra entrega: cafeteras, ollas, organizadores. Envío a todo México.",
        "intro": "Cafeteras, ollas, utensilios, organizadores y pequeños electrodomésticos para cocinar más fácil. Recibe en tu casa y paga contra entrega.",
    },
    "moda_accesorios": {
        "description": "Moda y accesorios con pago contra entrega: bolsos, relojes, lentes de sol, ropa y joyería. Envío a todo México.",
        "intro": "Bolsos, relojes, lentes de sol, billeteras, joyería y prendas para completar tu estilo. Pagas al recibir y puedes revisar el producto frente al repartidor.",
    },
    "juguetes": {
        "description": "Juguetes para niños con pago contra entrega: didácticos, autos, muñecas y juegos de mesa. Envío a todo México.",
        "intro": "Juguetes didácticos, autos, muñecas, juegos de mesa y regalos para todas las edades. Compra sin pagar por adelantado: pagas cuando llega el pedido.",
    },
    "deporte_fitness": {
        "description": "Deporte y fitness con pago contra entrega: implementos de gimnasio, yoga, ciclismo y más. Envío a todo México.",
        "intro": "Mancuernas, bandas, tapetes de yoga, accesorios de ciclismo y todo para entrenar en casa o al aire libre. Pagas contra entrega en todo México.",
    },
    "herramientas": {
        "description": "Herramientas con pago contra entrega: taladros, kits, medición y ferretería para el hogar. Envío a todo México.",
        "intro": "Taladros, kits de herramientas, medición, jardinería y ferretería para arreglos en casa o tu trabajo. Recibe el pedido y paga al repartidor.",
    },
    "mascotas": {
        "description": "Productos para mascotas con pago contra entrega: juguetes, collares, camas y accesorios. Envío a todo México.",
        "intro": "Juguetes, collares, camas, comederos y accesorios para perros y gatos. Pagas cuando el pedido llega a tu casa, en cualquier parte de México.",
    },
    "bebes": {
        "description": "Productos para bebés con pago contra entrega: cuidado, alimentación, juguetes y accesorios. Envío a todo México.",
        "intro": "Artículos de cuidado, alimentación, juguetes y accesorios para bebés y mamás. Revisa tu pedido al recibirlo y paga contra entrega.",
    },
    "vehiculos": {
        "description": "Accesorios para auto y moto con pago contra entrega: limpieza, organización y gadgets. Envío a todo México.",
        "intro": "Accesorios para auto y moto: soportes de celular, limpieza, organización, iluminación y gadgets para el camino. Pagas al recibir tu pedido.",
    },
    "papeleria": {
        "description": "Papelería y útiles con pago contra entrega: cuadernos, organización, oficina y manualidades. Envío a todo México.",
        "intro": "Cuadernos, útiles escolares, organización de oficina y manualidades. Pide en línea y paga contra entrega en cualquier parte de México.",
    },
    "fiesta_pinateria": {
        "description": "Fiesta y piñatería con pago contra entrega: decoración, globos y artículos para celebraciones. Envío a todo México.",
        "intro": "Globos, decoración, velas y todo para cumpleaños y celebraciones. Recibe en tu casa y paga cuando llegue el pedido.",
    },
    "seguridad": {
        "description": "Seguridad para el hogar con pago contra entrega: cámaras, alarmas, cerraduras y sensores. Envío a todo México.",
        "intro": "Cámaras de seguridad, alarmas, cerraduras y sensores para proteger tu casa o negocio. Pagas al recibir el pedido, sin pagos por adelantado.",
    },
    "otros": {
        "description": "Productos novedosos y útiles para el día a día con pago contra entrega. Envío a todo México.",
        "intro": "Productos novedosos, regalos y soluciones prácticas para el día a día. Pagas contra entrega y recibes en todo México.",
    },
}
