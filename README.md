# Pilucca

## How to use
1. build the image: 
    ```Bash
    docker build -t pilucca .
    ```
2. Copy the .env.example to your preferred location and add the correct Value

3. Open your crontab editor:
    ```Bash
    crontab -e
    ```
4. Add this line at the bottom tu run `it every monday at 8am`:
    ```Bash
    0 8 * * 1 docker run --rm --env-file /path/to/your/.env pilucca
    ```
      

