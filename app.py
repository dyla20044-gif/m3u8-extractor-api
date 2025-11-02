# 2. Configurar el monitoreo del tráfico de red (Tu código actual)
        def log_request(request):
            nonlocal m3u8_url
            url = request.url
            if ".m3u8" in url and "chunklist" not in url:
                if not m3u8_url:
                    m3u8_url = url
                    
        page.on("request", log_request)
        
        # 3. Navegar y forzar el inicio del streaming (¡PASOS NUEVOS!)
        try:
            await page.goto(video_url, wait_until="load", timeout=30000) # Cargar solo el HTML
            
            # --- Intento de clic en el botón de Play ---
            # Playwright espera a que el selector del botón de play sea visible
            # Los selectores pueden variar, pero probaremos con el más común (el reproductor grande)
            
            # 1. Esperar un botón de Play (generalmente un div grande o iframe)
            await page.wait_for_selector('button, .vjs-big-play-button, .play-button, iframe', timeout=10000)

            # 2. Hacer clic en el centro de la página o en el reproductor.
            # Este clic a menudo inicia el streaming o abre el iframe real del video.
            await page.click('body', force=True, position={'x': 500, 'y': 500})
            
            # 3. Esperar un tiempo prudente para que la solicitud .m3u8 aparezca en el tráfico
            await asyncio.sleep(5) 

        except Exception as e:
            # Captura errores de navegación o si no encuentra el botón
            await browser.close()
            return f"Error de navegación, clic o tiempo de espera: {e}"
            
        await browser.close()
        return m3u8_url
