# Lista de regalos · Navidad 2026

Cuatro listas (#alberto, #elena, #mama, #papa). Cualquiera con el enlace puede añadir, editar y quitar regalos en su lista.

- **Web**: HTML estático + una función de Netlify (`netlify/functions/lista.js`) que guarda los cambios en este repo.
- **Variable de Netlify**: `GH_TOKEN` = token de GitHub fine-grained, solo repo `lista`, permiso *Contents: Read and write*.
- **Añadir por enlace**: la función deja un pedido en `pedidos/` y la Acción `add.yml` (`scripts/add.py`) lee la web del producto y lo añade.
