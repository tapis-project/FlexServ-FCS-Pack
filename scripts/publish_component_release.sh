#!/usr/bin/env bash
# Publish already tested flat assets only after verifying their complete identity.
set -euo pipefail
tag=${1:?An existing release tag is required}
artifacts=${2:?An artifact directory is required}
: "${GITHUB_REPOSITORY:?Repository required}" "${GITHUB_SHA:?Source commit required}"
for program in gh jq sha256sum cmp sort; do command -v "$program" >/dev/null; done
actual=$(gh api "repos/$GITHUB_REPOSITORY/commits/$tag" --jq .sha)
[[ "$actual" == "$GITHUB_SHA" ]] || { echo 'Release tag does not match the workflow commit.' >&2; exit 1; }
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
# Exclude the inventory itself so reruns have the same manifest bytes.
(
    cd -- "$artifacts"
    export LC_ALL=C
    for file in *; do
        [[ "$file" == release-assets.sha256 ]] && continue
        [[ -f "$file" && ! -L "$file" ]] || { echo 'Release assets must be regular files.' >&2; exit 1; }
        sha256sum -- "$file"
    done
) > "$scratch/release-assets.sha256"
[[ -s "$scratch/release-assets.sha256" ]] || { echo 'No release assets.' >&2; exit 1; }
cp "$scratch/release-assets.sha256" "$artifacts/release-assets.sha256"
gh api "repos/$GITHUB_REPOSITORY/releases?per_page=100" --paginate --slurp > "$scratch/releases.json"
jq --arg tag "$tag" '[.[][]|select(.tag_name==$tag)]' "$scratch/releases.json" > "$scratch/matches.json"
[[ $(jq 'length' "$scratch/matches.json") -le 1 ]] || { echo 'Ambiguous release tag.' >&2; exit 1; }
if [[ $(jq 'length' "$scratch/matches.json") == 0 ]]; then
    gh release create "$tag" --repo "$GITHUB_REPOSITORY" --verify-tag --draft \
        --prerelease --title "$tag" --generate-notes "$artifacts"/*
    gh api "repos/$GITHUB_REPOSITORY/releases?per_page=100" --paginate --slurp > "$scratch/releases.json"
    jq --arg tag "$tag" '[.[][]|select(.tag_name==$tag)]' "$scratch/releases.json" > "$scratch/matches.json"
fi
[[ $(jq 'length' "$scratch/matches.json") == 1 ]] || { echo 'Expected one uploaded release.' >&2; exit 1; }
jq '.[0]' "$scratch/matches.json" > "$scratch/release.json"
# A published release is immutable to this helper; mismatches also leave drafts unpublished.
for file in "$artifacts"/*; do basename "$file"; done | LC_ALL=C sort > "$scratch/local-names"
jq -r '.assets[].name' "$scratch/release.json" | LC_ALL=C sort > "$scratch/remote-names"
cmp -s "$scratch/local-names" "$scratch/remote-names" || { echo 'Uploaded asset set mismatch.' >&2; exit 1; }
for file in "$artifacts"/*; do
    digest=$(sha256sum "$file"); digest=${digest%% *}
    bytes=$(wc -c < "$file")
    jq -e --arg name "${file##*/}" --arg digest "sha256:$digest" --argjson bytes "$bytes" \
        'any(.assets[]; .name==$name and .digest==$digest and .size==$bytes)' \
        "$scratch/release.json" >/dev/null || { echo 'Uploaded asset digest or size mismatch.' >&2; exit 1; }
done
if [[ $(jq -r '.draft' "$scratch/release.json") == true ]]; then
    release_id=$(jq -er '.id|numbers' "$scratch/release.json")
    gh api --method PATCH "repos/$GITHUB_REPOSITORY/releases/$release_id" -F draft=false > "$scratch/published.json"
    jq -e --arg tag "$tag" '.tag_name==$tag and (.draft|not)' "$scratch/published.json" >/dev/null
fi
echo "Verified component release: $tag"
