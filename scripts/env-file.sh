# Sourced by the scripts that copy .env values to a host. Values are never
# printed.

ENV_FILE="${ENV_FILE:-.env}"

# Read one key's value from the env file, taking the last definition and
# stripping surrounding quotes.
read_value() {
  sed -n "s/^[[:space:]]*$1=//p" "$ENV_FILE" \
    | tail -n 1 \
    | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}
