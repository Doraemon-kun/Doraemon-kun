import os
import json
import requests

def main():
    gist_id = os.environ.get('GIST_ID')
    gist_token = os.environ.get('GIST_TOKEN')

    if not gist_id or not gist_token:
        return

    gh_headers = {"Authorization": f"Bearer {gist_token}"}
    url = f"https://api.github.com/gists/{gist_id}"

    res = requests.get(url, headers=gh_headers)
    if res.status_code != 200:
        return

    files = res.json().get('files', {})
    json_file = next((n for n in files if n.lower().endswith('.json')), None)
    m3u_file = next((n for n in files if n.lower().endswith('.ts')), None)

    if not json_file or not m3u_file:
        return

    channels = json.loads(files[json_file]['content'])
    m3u_lines = files[m3u_file]['content'].splitlines()

    jwk_cache = {}
    upstream_cache = {}
    updated = False
    custom_headers = {"User-Agent": "Wink/1.31.1"}

    for ch in channels:
        mode = ch.get('mode', 'clearkey')
        tvg_id = ch.get('tvg-id')
        c_name_mine = ch.get('channel_name')

        if mode == 'clearkey':
            c_link = ch.get('channel_link')
            l_link = ch.get('license_link')

            if l_link is None or tvg_id is None or not c_name_mine:
                continue

            if l_link not in jwk_cache:
                try:
                    r = requests.get(l_link, headers=custom_headers, timeout=10)
                    if r.status_code == 200:
                        jwk_cache[l_link] = json.dumps(r.json(), separators=(',', ':'))
                except:
                    pass

            jwk = jwk_cache.get(l_link)
            if not jwk:
                continue

            for i, line in enumerate(m3u_lines):
                if line.startswith('#EXTINF') and ',' in line:
                    line_name = line.rsplit(',', 1)[-1].strip()
                    tvg_match = (tvg_id == "") or (f'tvg-id="{tvg_id}"' in line)

                    if tvg_match and line_name == c_name_mine.strip():
                        for j in range(i + 1, len(m3u_lines)):
                            if m3u_lines[j].startswith('#KODIPROP:inputstream.adaptive.license_key='):
                                new_line = f'#KODIPROP:inputstream.adaptive.license_key={jwk}'
                                if m3u_lines[j] != new_line:
                                    m3u_lines[j] = new_line
                                    updated = True

                            elif not m3u_lines[j].startswith('#'):
                                if c_link and m3u_lines[j].strip() != c_link.strip():
                                    m3u_lines[j] = c_link
                                    updated = True
                                break
                        break

        elif mode == 'token':
            c_name_up = ch.get('channel_name_upstream')
            up_link = ch.get('upstream_link')

            if tvg_id is None or not c_name_up or not c_name_mine or not up_link:
                continue

            if up_link not in upstream_cache:
                try:
                    r = requests.get(up_link, headers=custom_headers, timeout=15)
                    if r.status_code == 200:
                        upstream_cache[up_link] = r.text.splitlines()
                except:
                    pass

            up_lines = upstream_cache.get(up_link)
            if not up_lines:
                continue

            new_url = None
            for i, line in enumerate(up_lines):
                if line.startswith('#EXTINF') and ',' in line:
                    line_name = line.rsplit(',', 1)[-1].strip()
                    tvg_match = (tvg_id == "") or (f'tvg-id="{tvg_id}"' in line)

                    if tvg_match and line_name == c_name_up.strip():
                        for j in range(i + 1, len(up_lines)):
                            if not up_lines[j].startswith('#'):
                                new_url = up_lines[j].strip()
                                break
                        break

            if not new_url:
                continue

            for i, line in enumerate(m3u_lines):
                if line.startswith('#EXTINF') and ',' in line:
                    line_name = line.rsplit(',', 1)[-1].strip()
                    tvg_match = (tvg_id == "") or (f'tvg-id="{tvg_id}"' in line)

                    if tvg_match and line_name == c_name_mine.strip():
                        for j in range(i + 1, len(m3u_lines)):
                            if not m3u_lines[j].startswith('#'):
                                if m3u_lines[j].strip() != new_url:
                                    m3u_lines[j] = new_url
                                    updated = True
                                break
                        break

    if updated:
        payload = {"files": {m3u_file: {"content": '\n'.join(m3u_lines)}}}
        requests.patch(url, headers=gh_headers, json=payload)

if __name__ == '__main__':
    main()
