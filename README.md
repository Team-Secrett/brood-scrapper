# brood-scrapper

Scrapper distribuido que dado un conjunto de dominios web y una profundidad realiza scrapping a estos hasta dicha profundidad.

#

Autores:
- Samuel David Suárez Rodríguez, C412 - [@samueldsr99](github.com/samueldsr99)
- Enmanuel Verdesia Suárez, C411 - [@svex99](github.comm/svex99)

#

## Arquitectura

El sistema esta constituido por tres tipos de nodos:

- **Client:** Carga las urls a analizar y las probee a los workers.
- **Worker:** Recibe las urls de los clientes y consulta la disponibildad de estas en los nodos storage para evitar tener que hacer una peticion web vía http, el resultado lo devuelven a los clientes y si fue necesario hacer scrapping, dado que no estaba *cacheada* la petición, se le envía la actualización a los nodos de almacenamiento.
- **Storage:** Procesan las consultas a caché de los workers y responden con el contenido, si es un *hit*, o no, en caso contrario. Propagan las actualizaciones a los demás nodos de almacenamiento.

El descubrimiento en la red es mediante grupos multicast y cada nodo se adapta a la cantidad de nodos disponibles del tipo que necesita. Estableciendo una relación de necesidad o dependencia entre los nodos se puede decir que los clientes dependen de los workers y estos de los storage, pero no de forma absoluta porque el sistema continúa funcionando sin nodos de almacenamiento, realizando los workers las consultas directo a la web.

### Conexiones Client - Worker

En la imagen se observa el grupo multicast 1, en este los workers envían beacons con su id y el puerto por el que esta escuchando, por tanto los clientes que escuchan en ese grupo pueden saber la disponibilidad de workers en la red, conectarse a los que encuentren y desconectarse de los que después de cierto intervalo de tiempo no den señales de vida.

Al un ciente conectarse a un worker se establece una conexión entre sockets zmq de tipo DEALER (cleinte) -> ROUTER (worker), esto ofrece la ventaja de que al un cliente conectarse a más de un worker, el cliente se encargue del balanceo de carga en las peticiones que hace.

### Conexiones Worker - Storage

En el grupo multicast 2 los nodos storage envían beacons de igual forma con su id y puerto por el que escuchan las conexiones de los workers. De igual forma al caso anterior la conexión se establece entre DEALER (worker) -> ROUTER (storage) lo que garantiza balanceo de carga en las peticiones a los diferentes storages.

Cuando un worker realiza el scrapping a una dirección web, esto fue o bien porque no había servicio de almacenamiento disponible o bien porque se consultó previamente y no tenia la información, se necesita enivar un update a los nodos de almacenamiento. Este update se envía en un solo mensaje y solo a uno de los storage disponibles (esto lo selecciona el socket de forma interna), el storage que lo reciba es el encargado de propagarlo a los demás para mantener la consistencia entre las réplicas.

### Conexiones Storage - Storage
En el mismo grupo multicast 2 van a estar escuchando los nodos de almacenamiento. De esta forma descubren los otros nodos del mismo tipo que hay en la red, los que deben hacerle llegar las updates de los workers. Es decir cada vez que un nodo storage recibe un update de un worker la propaga a los demás.

Adicionalmente permite que cuando un nodo de almacenamiento entre al sistema le pueda solicitar la información a otro nodo y así replicarla localmente para que en caso de que aquel nodo muera no se pierda la información almacenada.


### Ping messages

- **workers -> clients**: `'w <worker_id> <worker_port>'`, (max len: 12)
    - max len(worker_id): 4
    - max len(worker_port): 5


### Request/Response messages

- Request from client to worker

    ```json
    {
        "id": "client-id",
        "url": "www.example.com"
    }
    ```

- Response from worker to client

    ```json
    {
        "url": "www.example.com",
        "hit": true,  // or false
        "content": "<h1>html code for www.example.com</h1>"
    }
    ```

- Request from worker to storage

    ```json
    {
        "id": "client-id",
        "url": "www.example.com"
    }
    ```

- Rsponse from strorage to worker

    ```json
    {
        "id": "client-id",
        "url": "www.example.com",
        "hit": true,  // or false
        "content": "<h1>html code for www.example.com</h1>"
    }
    ```

- Update from worker to strorage

    ```json
    {
        "url": "www.example.com",
        "content": "<h1>html code for www.example.com</h1>",
        "spread": true
    }
    ```

- Update cache request

    ```json
    {
        "id": "storage-id",
        "new": true,
        "updateme": true,
    }
    ```

- Update from storage to storage

    ```json
    {
        "url": "www.example.com",
        "content": "<h1>html code for www.example.com</h1>",
        "spread": false
    }
    ```