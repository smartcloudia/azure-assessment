#!/bin/bash
pwsh -c Export-AzViz -ResourceGroup $1 -Theme light -OutputFormat png -Show
rm -f $1.png
mv /tmp/output.png ./$1.png
scp $1.png ip:/personalweb/informe2/

