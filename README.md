# Lista de regalos

Web estática de una sola página (`index.html`) con mi lista de deseos de Navidad.

## Cómo añadir un regalo

Abre `index.html` y añade una entrada al bloque `WISHES`, dentro de `DATOS`:

```js
{ n:'Nombre', p:25, l:'https://enlace-al-producto', o:'Nota', img:'fotos/foto.jpg' }
```

Las fotos pueden ser un enlace o un archivo subido a la carpeta `fotos/`.
Si una foto no carga, se ve un cuadro de color con la inicial.

## Publicar

Activa GitHub Pages en *Settings → Pages* (rama `main`, carpeta raíz).
