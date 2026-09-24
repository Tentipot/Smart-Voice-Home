# STT validation pilot_01 — аудио каталог

Дата на приемане: 2026-09-25. Всички 24 записа са прослушани и приети от
потребителя. Те са референтни входове за бъдещ STT тест; не съдържат резултат
от финален STT и не трябва да се използват като доказателство за точност.

Форматът е 16 kHz, mono, PCM16. Тихите части преди и след речта са запазени.
Playback сигналите са добавяни само при прослушване и не са част от WAV файла.
`rms` е измерен върху целия запис. SHA256 идентифицира точното съдържание.

| ID | Език | Какво е казано | WAV | s | RMS | SHA256 |
| --- | --- | --- | --- | ---: | ---: | --- |
| BG01 | BG | Аурора, намали силата на звука до двадесет процента. | `BG01_7950771aedde4140805d0ae430913263.wav` | 5.50 | 0.03423636 | `04d515d14357be54142f5c218cc862714e1d0e4edab75d8bdf92a847f3a9261` |
| BG02 | BG | Аурора, увеличи силата на звука до шестдесет процента. | `BG02_44ba8b29e70240d681ee58fbba162427.wav` | 5.90 | 0.03199894 | `b7a2918dfc3562af939b30159e8fd6683b611f033b12a752d13741c8b9896ed0` |
| BG03 | BG | Аурора, включи малката лампа до дивана. | `BG03_34ec6f4c0c3d4076b93606c3523c32a0.wav` | 5.20 | 0.04053264 | `3f1dc3128b0615d456bbb6f7781b4e138f1e16f859b57b75b785f5b7b56a96a1` |
| BG04 | BG | Аурора, изключи осветлението над масата. | `BG04_c4362c64e14048289f8e45db3547b831.wav` | 5.20 | 0.03945600 | `c248f4d347c849784b0981522bb95ee49d7e22d9506a9e53e1d6d368d6487a59` |
| BG05 | BG | Аурора, спри възпроизвеждането в кухнята. | `BG05_c32b5d7245314f4693d93140b6351f71.wav` | 4.80 | 0.03826066 | `37e84e7b555f5204585694929f86a5a77777a8fb49d6b7516dc20d2b1a36c067` |
| BG06 | BG | Аурора, продължи възпроизвеждането в спалнята. | `BG06_056e348ba9af496784f5d09431683ef9.wav` | 5.30 | 0.04087484 | `e042aacafc896dc315e7f246cb2b35e82beedfe779defffe3f465677af1001e3` |
| BG07 | BG | Аурора, каква ще бъде температурата утре сутрин? | `BG07_d0d81ddb7bec4be6806b4d8d094d19b9.wav` | 5.70 | 0.03422203 | `5e6ffe5a129fda2e6f4f852309e4cea01b08f8926885a9388ba000ef20fee1da` |
| BG08 | BG | Аурора, след колко минути ще стане осем часът? | `BG08_38cc5ee88de4415b9231a395f37aae51.wav` | 5.40 | 0.03605270 | `e339e6d3a6fe45b026f79c7ceba6e403daae8a2a675755f0135a425389146198` |
| EN01 | EN | Aurora, reduce the speaker volume to twenty percent. | `EN01_a0ceee5fdde547e7a0e6db0370c9c1a6.wav` | 5.90 | 0.04187711 | `479dac0037702b4e1fc1314ce963bdb0c67ea6a19ced7b2e31be872dbc1752af` |
| EN02 | EN | Aurora, increase the speaker volume to sixty percent. | `EN02_d12205a611ad45db820ee90ff24e301c.wav` | 6.10 | 0.03947683 | `064ac6fdd25744fa2ee3a049a13eb333a606ace6950bd90a53e186850d84cd79` |
| EN03 | EN | Aurora, switch on the small lamp beside the sofa. | `EN03_e8fc2b0a968c4cbd8387950fc73338c4.wav` | 5.80 | 0.03667037 | `c11b02e3c7359e0ca9fa7092f528b661d11562c923cae543596b2d47a8ad8bb6` |
| EN04 | EN | Aurora, switch off the light above the table. | `EN04_3e99a2c113764e63bfb2e8a8ba220db9.wav` | 5.90 | 0.03912579 | `4be0e915434108f50872c4ac9fff419df56b42ba3a3d3f1f9e1ca5ed1151ec69` |
| EN05 | EN | Aurora, pause playback in the kitchen. | `EN05_b58eab81cc0b436abee469e54e066d34.wav` | 5.60 | 0.03609912 | `9901bb09befb48fd733f0cd15c5c44893a0c7e2e74a0c6b7ab8dcf226fc2b44b` |
| EN06 | EN | Aurora, resume playback in the bedroom. | `EN06_668e9d55fec0435c9dd8f23d06b80e60.wav` | 5.00 | 0.03950751 | `d365a4d7f438d61c526e62ac048949e6392f66c90e02cc3e15ffaa715922a745` |
| EN07 | EN | Aurora, what will the temperature be tomorrow morning? | `EN07_cbec2ca646a4434697618e2b244f38c9.wav` | 6.20 | 0.03548878 | `67a2a6d8467aea4e1f86a7fc54bed1177042ed99303dd43fa907f3b5603e9a09` |
| EN08 | EN | Aurora, how many minutes are left until eight? | `EN08_d239ef2148ed47168fa5c5ceb8a73e92.wav` | 6.00 | 0.03370010 | `ca025f2e0752ec14268ea9a1cc751e6a74669bfe8650d75098b74224daee6a67` |
| MX01 | MIXED | Аурора, пусни Here Comes the Sun в Spotify. | `MX01_84cc478d01704eb8a8a76ae0b8cbecdf.wav` | 5.50 | 0.04050585 | `b737a601bb59dab65ae3fbb766fc874dd8c6c1967cf4bc088de505c23ff76364` |
| MX02 | MIXED | Аурора, потърси live concert на Pink Floyd. | `MX02_6e0cb4d1aed04cb7ba3ece745f095dc0.wav` | 7.10 | 0.03501548 | `a9486f5a149021e40fd78f3cbb6c643d5ea405ed45d09692361ad797c7e5f136` |
| MX03 | MIXED | Аурора, намали звука, then pause the music. | `MX03_5773bc66c29545b492010e65bb9a4dc1.wav` | 6.20 | 0.04209358 | `d6ce88417a33c27d576b1f3932d0310822fa7893eef7594b95dfe9d1694c1443` |
| MX04 | MIXED | Аурора, включи лампата, but keep the music playing. | `MX04_9ee8f99c056c476b96bd695a0c62c89c.wav` | 5.80 | 0.03674410 | `ac976ca04b2799f4fb6b146c4be110f1e22130b51ed31b96a67670603604886d` |
| MX05 | MIXED | Aurora, play the song Хубава си, моя горо. | `MX05_08930a1eb736490fae01901a52563a1d.wav` | 6.10 | 0.03950121 | `4110dbe36e1727280b5730a80221d7c0ed1b74aafaf3a4b64c02fb8cdfb1c703` |
| MX06 | MIXED | Aurora, search for българска народна музика. | `MX06_15969fc1f86142dcaf7224157b25ae46.wav` | 6.30 | 0.03814675 | `1ffcba37f39aff3cba746ab6bffe192669d446b457bd862e8335af0d3833a14d` |
| MX07 | MIXED | Aurora, pause the music, после изключи лампата. | `MX07_7c36abcfc9b347d8b0c80afdfe4cd362.wav` | 6.20 | 0.03821496 | `1435f883f08a453febcc0b63cc202caeb374a3fa63f6e7f29601d0499f6de0cd` |
| MX08 | MIXED | Aurora, turn on the light, но не променяй звука. | `MX08_9577dfa6ef224a7fabb95432d5cec6d7.wav` | 6.80 | 0.04292713 | `0047ac2b86c0cd7a6a92847534a6666334f97baaf3fab2db1c22eaff3b88b957` |

Първият MX04 WAV е отхвърлен заради грешно произнасяне и остава в
manifest-а само като rejected attempt; приетият файл е посоченият втори.
