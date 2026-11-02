## What is the digital onboarding process?
Digital onboarding lets you open your account online. You enter your email, upload a photo of your identity document, and we read the data automatically. No branch visit and no manual paperwork are needed. Also known as KYC (Know Your Customer), or registro de clientes.

## Which documents can I use?
You can upload a Peruvian DNI (documento nacional de identidad), a foreigner card (carné de extranjería) or a passport. The document must be valid, original and not expired. Photocopies and screenshots of other screens are not accepted.

## Which image formats and sizes are accepted?
Only JPG and PNG images are accepted, up to 5 MB each. The image should be at least 300 pixels on its shortest side. PDF files and other formats are rejected with an unsupported file type message.

## How do I take a good photo of my document?
Place the document on a flat, dark surface in good natural light. Avoid glare, shadows and cut-off edges. Keep the camera steady so the whole document is sharp and all the text is readable. Blurry photos are rejected, and you can simply retake the photo.

## Why was my image rejected as blurry?
The system measures the sharpness of the image before reading it. If the text is out of focus, too dark or shaken, the image is rejected as blurry. Retake the photo with steady hands, more light and no glare, then upload it again.

## What data is extracted from my document?
We extract your full name, your document number and the document type. We also record how confident the reading is, shown as the OCR confidence percentage. Your email and the extracted data are saved together with the date and time of the registration.

## What does the OCR confidence mean?
It is a percentage that tells how sure the artificial intelligence is that it read your name and document number correctly. Records with high confidence are marked as Verified. Records with lower confidence are marked as Needs review, and an operator will check them manually.

## What does the Needs review status mean?
It means the automatic reading was not confident enough, or the document number did not match the expected format. This is not a rejection. A bank operator will review the record manually and may contact you by email.

## Do you store my document photo?
No. The photo is sent to the artificial intelligence service only to read the text and is not saved in our database. We keep your email, your name, your document number, the confidence and a technical fingerprint (hash) of the image, together with the timestamp.

## Is my information secure?
Secrets such as API keys are kept in environment variables, never in the source code. The image is validated before processing and the connection to the service should use HTTPS. Only the minimum data needed for the registration is stored.

## How long does the process take?
Reading a document normally takes a few seconds. The page shows a loading state while the document is processed. If the AI service is busy you may be asked to try again in a minute.

## What if the system could not read my name or number?
Retake the photo so that the whole document is visible, with no glare and no cropped edges, and upload it again. If the problem continues, contact customer support and an operator can complete the registration manually.

## Can I register more than once with the same email?
Yes. Each upload creates a new onboarding record linked to the same customer email, so you can retry after a failed or low confidence attempt.
