---
layout: default
title: "Home"
permalink: /
---
# {{ site.title }}

{% include installer.html %}

### Latest Entries (Rolling {{ site.recent_posts_limit | default: 10 }})

<!-- START_RECENT_POSTS -->
<div class="recent-posts-grid">
{%- assign limit_n = site.recent_posts_limit | default: 10 -%}
{%- for post in site.posts limit: limit_n -%}
  {%- assign raw_img = post.image.path | default: post.image | default: site.default_post_thumb -%}
  {%- assign raw_alt = post.image.alt | default: post.title -%}
  {%- assign summary = post.meta_description | default: post.excerpt | default: post.description | strip_html | normalize_whitespace | truncate: 160 -%}
  <a class="recent-post-card" href="{{ post.url | relative_url }}">
    {%- if raw_img and raw_img != "" %}
    <img class="recent-post-thumb" src="{{ raw_img | relative_url }}" alt="{{ raw_alt | escape }}" width="480" height="252" loading="lazy">
    {%- endif %}
    <div class="recent-post-body">
      <span class="recent-post-date">{{ post.date | date: "%Y-%m-%d" }}</span>
      <strong class="recent-post-title">{{ post.title | escape }}</strong>
      <span class="recent-post-desc">{{ summary | escape }}</span>
    </div>
  </a>
{%- endfor -%}
  <!-- TODO: Pagination / Archive Horizon Hook (data-next-cursor / stabilized hubs) -->
</div>
<!-- END_RECENT_POSTS -->
