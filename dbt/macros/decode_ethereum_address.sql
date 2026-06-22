-- 목적: Ethereum ABI topic/data decoding 반복식 공통화.
-- 규칙: topic address는 32-byte word. 마지막 20 bytes가 실제 address.
{% macro decode_ethereum_address(topic_expr) -%}
case
  when {{ topic_expr }} is null then null
  when regexp_matches(lower({{ topic_expr }}), '^0x[0-9a-f]{64}$')
    then lower('0x' || right({{ topic_expr }}, 40))
  else null
end
{%- endmacro %}
