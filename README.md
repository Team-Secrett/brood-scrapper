# brood-scrapper

### Ping messages

- **workers -> clients**: `'w <worker_id> <worker_port>'`, (max len: 12)
    - max len(worker_id): 4
    - max len(worker_port): 5


### Request/Response messages

- Request from client to worker

    ```json
    {
        'url': 'www.example.com'
    }
    ```

- Response from worker to client

    ```json
    {
        'url': 'www.example.com'.
        'html': '<h1>html code for www.example.com</h1>'
    }
    ```
