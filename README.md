# EpubSplit

This is a repository for the EpubSplit Calibre Plugin.

Most discussion of this plugin takes place in the [EpubSplit Calibre Plugin forum].

Splitting omnibus eBooks into multiple eBooks seems to be a common request, but there haven't been many tools to do so without a lot of hand editing.

This plugin provides the ability to create new EPUBs by splitting off part of an existing (non-DRM) EPUB format eBook.

Main Features of EpubSplit Plugin:

* Present the user with a list of 'split lines' in the existing EPUB. The beginning of each file listed in the manifest spine and each Table of Contents(TOC) entry. <guide> tagged files are also indicated.
* 'Preview' contents of each 'split line' as a tooltip over the HREF.
* Allow user to edit the TOC entry(s) for each 'line'.
* Select one or more of the offered lines to include in the new eBook,
* Edit the metadata for the new split eBook, and then,
* Extract only the selected contents of the source EPUB into the new EPUB,
* Scan the selected content for CSS & image links for additional files to include,
* Scan the selected content for internal links and anchors and update links that need to point to different filenames,
* Use the metadata entered into calibre for the new eBook (including cover) as the metadata in the new EPUB.
* Return to list of source EPUB sections after creating a new split EPUB.
* Configure which metadata from source EPUB to copy to new eBook, now offering more of the standard metadata and custom columns.
* Configurably populate a custom column with the source book title/author/etc.
* CLI via calibre-debug --run-plugin

[EpubSplit Calibre Plugin forum]: http://www.mobileread.com/forums/showthread.php?t=178799


# Programmatic Splitting (CLI)

Make epubsplit.py executable and in PATH. Then the following zsh function can split your epubs automagically!

```
# Adapted from my scripts at https://github.com/NightMachinary/.shells/blob/master/scripts/zsh/auto-load/others/ebooks.zsh
epubsplit () {
 local file="$1"
 local title="${2:-Unknown title}"
 local pLn='^\s*Line Number:\s+(\d+)' 
 local p1="${esP1:-toc:\s+\['\D*(\d+).*'\]}" 
 local p2="${esP2:-id:\s+[cC]\D*(\d+)}" 
 local i=0 
 local n="${esN:-3}" 
 local n1=$((n+1)) 
 local hasChanged='' 
 local lm1='' 
 local lm2='' 
 local alreadyNoticed='' 
 local currentSplit=0 
 local split=()
 for line in "${(@f)$(epubsplit.py "$file")}"
 do
  hasChanged='' 
  [[ "$line" =~ "$pLn" ]] && {
   split+="$match[1]" 
   alreadyNoticed='' 
   continue
  }
  [[ "$line" =~ "$p1" ]] && {
   [[ "$match[1]" != "$lm1" ]] && {
    test -z "$alreadyNoticed" && hasChanged='y' 
    alreadyNoticed=y 
   }
   lm1="$match[1]" 
  }
  [[ "$line" =~ "$p2" ]] && {
   [[ "$match[1]" != "$lm2" ]] && {
    test -z "$alreadyNoticed" && hasChanged='y' 
    alreadyNoticed=y 
   }
   lm2="$match[1]" 
  }
  test -n "$hasChanged" && {
  
   i=$(( (i+1) % n1 )) 
   [[ "$i" == 0 ]] && {
    i=1 
    epubsplit.py --title "p${currentSplit} $title" -o "p${currentSplit} ""$file" "$file" "${(@)split[1,-2]}"
    currentSplit=$((currentSplit+1)) 
    split=($split[-1]) 
   }
  }
 done
 test -z "${split[*]}" || epubsplit.py --title "p${currentSplit} $title" -o "p${currentSplit} ""$file" "$file" "${split[@]}"
}
```

```
# usage
epubsplit somegile.epub "its title"
# By default, a split happens roughly every 3 chapters. You can customize this like this:
esN=8 epubsplit ...
# You can further customize the chapter detection heuristics by setting esP1 and esP2, but you need to understand the code to do that.
```
