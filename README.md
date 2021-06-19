# brood-scrapper

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