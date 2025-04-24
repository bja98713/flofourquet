from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from .models import Facturation, Code, Paiement
from .forms import FacturationForm
from django.utils import timezone

import pdfkit
from django.conf import settings

# Vue de recherche
class FacturationSearchListView(ListView):
    model = Facturation
    template_name = 'comptabilite/facturation_search_list.html'
    context_object_name = 'facturations'

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(dn__icontains=query) |
                Q(nom__icontains=query) |
                Q(prenom__icontains=query) |
                Q(numero_facture__icontains=query) |
                Q(date_acte__icontains=query)
            )
        return queryset

# Vue pour la liste des facturations
class FacturationListView(ListView):
    model = Facturation
    template_name = 'comptabilite/facturation_list.html'
    context_object_name = 'facturations'

# Vue de création avec le formulaire personnalisé
import json
from django.views.generic import CreateView
from django.urls import reverse_lazy
from .models import Facturation, Code
from .forms import FacturationForm

class FacturationCreateView(CreateView):
    model = Facturation
    form_class = FacturationForm
    template_name = 'comptabilite/facturation_form.html'
    success_url = reverse_lazy('facturation_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Charger tous les codes et préparer un dictionnaire avec les données à transmettre
        codes = Code.objects.all()
        codes_data = {}
        for code in codes:
            # On indexe par la valeur du champ code_acte, ou vous pouvez utiliser code.pk
            codes_data[code.code_acte] = {
                'total_acte': str(code.total_acte),
                'tiers_payant': str(code.tiers_payant),
                'total_paye': str(code.total_paye),
            }
        context['codes_data'] = json.dumps(codes_data)
        return context

# Vue de mise à jour avec le formulaire personnalisé
class FacturationUpdateView(UpdateView):
    model = Facturation
    form_class = FacturationForm
    template_name = 'comptabilite/facturation_form.html'
    success_url = reverse_lazy('facturation_list')

class FacturationDeleteView(DeleteView):
    model = Facturation
    template_name = 'comptabilite/facturation_confirm_delete.html'
    success_url = reverse_lazy('facturation_list')

class FacturationDetailView(DetailView):
    model = Facturation
    template_name = 'comptabilite/facturation_detail.html'
    context_object_name = 'facturation'

def check_dn(request):
    dn = request.GET.get('dn')
    if dn:
        try:
            fact = Facturation.objects.filter(dn=dn).latest('id')
            data = {
                'dn': fact.dn,
                'nom': fact.nom,
                'prenom': fact.prenom,
                'date_naissance': fact.date_naissance.strftime('%Y-%m-%d'),  # Format ISO attendu par type="date"
            }
            return JsonResponse({'exists': True, 'patient': data})
        except Facturation.DoesNotExist:
            pass
    return JsonResponse({'exists': False})

def check_acte(request):
    code_value = request.GET.get('code')
    if code_value:
        try:
            # Récupère l'objet Code par sa clé primaire
            code_obj = Code.objects.get(pk=code_value)
            data = {
                'total_acte': str(int(round(code_obj.total_acte))),
                'tiers_payant': str(int(round(code_obj.tiers_payant))),
                'total_paye': str(int(round(code_obj.total_paye))),
            }
            return JsonResponse({'exists': True, 'data': data})
        except Code.DoesNotExist:
            return JsonResponse({'exists': False})
    return JsonResponse({'exists': False})


def print_facture(request, pk):
    facture = Facturation.objects.get(pk=pk)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="facture_{}.pdf"'.format(facture.numero_facture or facture.pk)
    c = canvas.Canvas(response, pagesize=A4)
    largeur, hauteur = A4

    # Récupération des données
    nom = facture.nom
    prenom = facture.prenom
    date_naissance = facture.date_naissance.strftime("%d/%m/%Y") if facture.date_naissance else ""
    dn = facture.dn
    date_facture = facture.date_facture.strftime("%d/%m/%Y") if facture.date_facture else ""
    total_acte = str(facture.total_acte)
    total_paye = str(facture.total_paye)
    tiers_payant = str(facture.tiers_payant)

    code_obj = facture.code_acte
    if code_obj:
        code_acte_normal = code_obj.code_acte_normal or ""
        variable_1 = code_obj.variable_1 or ""
        modificateur = code_obj.modificateur or ""
        variable_2 = code_obj.variable_2 or ""
        ps = "oui" if code_obj.parcours_soin else "non"
    else:
        code_acte_normal = ""
        variable_1 = ""
        modificateur = ""
        variable_2 = ""
        ps = ""

    if code_obj and code_obj.medecin:
        nom_medecin = code_obj.medecin.nom_medecin
        nom_clinique = code_obj.medecin.nom_clinique
        code_m = code_obj.medecin.code_m
    else:
        nom_medecin = ""
        nom_clinique = ""
        code_m = ""

    regime_lm = ""
    if hasattr(facture, 'regime_lm'):
        regime_lm = "oui" if facture.regime_lm else "non"

    c.drawString(2.0 * cm, hauteur - 3.7 * cm, f"{nom}")
    c.drawString(12.5 * cm, hauteur - 3.7 * cm, f"{prenom}")
    c.drawString(16.0 * cm, hauteur - 4.7 * cm, f"{date_naissance}")
    c.drawString(2.0 * cm, hauteur - 4.7 * cm, f"{dn}")
    c.drawString(2.0 * cm, hauteur - 13.0 * cm, f"{nom_medecin}")
    c.drawString(2.0 * cm, hauteur - 13.5 * cm, f"{nom_clinique}")
    c.drawString(10.5 * cm, hauteur - 12.6 * cm, f"{code_m}")
    c.drawString(2.5 * cm, hauteur - 14.8 * cm, f"{ps}")
    c.drawString(0.3 * cm, hauteur - 16.5 * cm, f"{regime_lm}")
    c.drawString(0.5 * cm, hauteur - 20.3 * cm, f"{date_facture}")
    c.drawString(4.0 * cm, hauteur - 20.3 * cm, f"{code_acte_normal}")
    c.drawString(7.0 * cm, hauteur - 20.3 * cm, f"{variable_1}")
    c.drawString(7.5 * cm, hauteur - 20.3 * cm, f"{modificateur}")
    c.drawString(11.5 * cm, hauteur - 20.3 * cm, f"{variable_2}")
    c.drawString(12.5 * cm, hauteur - 20.3 * cm, f"{total_acte}")
    c.drawString(10.0 * cm, hauteur - 24.3 * cm, f"{total_acte}")
    if facture.regime_lm:
        c.drawString(7.5 * cm, hauteur - 27.6 * cm, f"{total_paye}")
        c.drawString(11.5 * cm, hauteur - 27.6 * cm, f"{tiers_payant}")

    c.save()
    return response

from datetime import date
from django.shortcuts import render
from django.db.models import Q
from .models import Facturation

def create_bordereau(request):
    """
    Cette vue crée un bordereau pour les factures destinées à être encaissées.
    Les factures sont sélectionnées si leur tiers_payant > 0 et si le numéro de bordereau n'est pas défini.
    Pour chaque facture, on met à jour le numéro de bordereau et la date du bordereau.
    Le numéro de bordereau est généré selon le format "M-année-mois-semaine-jour_annee".
    La vue calcule également le nombre de factures et la somme totale du tiers_payant.
    """
    # Sélectionner les factures à traiter
    factures = Facturation.objects.filter(tiers_payant__gt=0).filter(
        Q(numero_bordereau__isnull=True) | Q(numero_bordereau="")
    )
    
    if not factures.exists():
        return render(request, 'comptabilite/bordereau.html', {
            'error': "Aucune facture à traiter pour le bordereau."
        })
    
    # Génération du numéro de bordereau
    today = date.today()
    year = today.year
    month = today.month
    week = today.isocalendar()[1]
    day_of_year = today.timetuple().tm_yday
    num_bordereau = f"M-{year}-{month:02d}-{week:02d}-{day_of_year:03d}"
    
    # Mettre à jour chaque facture avec le numéro et la date du bordereau
    for facture in factures:
        facture.numero_bordereau = num_bordereau
        facture.date_bordereau = today
        facture.save()
    
    # Calculer le nombre de factures et la somme totale du tiers_payant
    count = factures.count()
    total_tiers_payant = sum(facture.tiers_payant for facture in factures)
    
    context = {
        'factures': factures,
        'num_bordereau': num_bordereau,
        'date_bordereau': today.strftime("%d/%m/%Y"),
        'count': count,
        'total_tiers_payant': total_tiers_payant,
    }
    return render(request, 'comptabilite/bordereau.html', context)

import tempfile
from django.template.loader import render_to_string
from django.http import HttpResponse
from weasyprint import HTML
from datetime import date
from .models import Facturation

def print_bordereau(request, num_bordereau):
    """
    Génère un PDF pour le bordereau identifié par 'num_bordereau'.
    Suppose que toutes les factures associées ont déjà num_bordereau = ce code.
    """
    # Récupérer les factures associées
    factures = Facturation.objects.filter(numero_bordereau=num_bordereau)
    if not factures.exists():
        return HttpResponse("Aucune facture trouvée pour ce bordereau.", status=404)
    
    # Extraire les infos
    count = factures.count()
    total_tiers_payant = sum(f.tiers_payant for f in factures)

    # On suppose que la date_bordereau est la même pour toutes les factures
    # ou on utilise la date du jour par défaut.
    date_bordereau = factures.first().date_bordereau or date.today()

    context = {
        'num_bordereau': num_bordereau,
        'date_bordereau': date_bordereau.strftime("%d/%m/%Y"),
        'count': count,
        'total_tiers_payant': total_tiers_payant,
        'factures': factures,
    }

    # Rendre le template bordereau_pdf.html en chaîne HTML
    html_string = render_to_string('comptabilite/bordereau_pdf.html', context)

    # Convertir en PDF
    pdf_file = HTML(string=html_string).write_pdf()

    # Soit on enregistre sur disque, soit on renvoie comme réponse HTTP
    # Pour enregistrer sur disque, vous pourriez faire :
    filename = f"{num_bordereau}.pdf"
    with open(filename, "wb") as f:
        f.write(pdf_file)

    # Pour renvoyer le PDF au navigateur :
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

from django.views.generic import ListView
from django.db.models import Q
from datetime import datetime
from .models import Facturation

# comptabilite/views.py
from django.views.generic import ListView
from django.db.models import Sum
from .models import Facturation
from datetime import datetime

class ActivityListView(ListView):
    model = Facturation
    template_name = 'comptabilite/activity_list.html'
    context_object_name = 'factures'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Récupérer les paramètres de filtre
        date_str = self.request.GET.get('date')          # format attendu: 'YYYY-MM-DD' ou 'DD/MM/YYYY'
        start_date_str = self.request.GET.get('start_date')  # format ISO ou européen
        end_date_str = self.request.GET.get('end_date')
        year_str = self.request.GET.get('year')            # par exemple: '2025'
        
        if date_str:
            # Tenter de parser en format ISO, sinon format européen
            try:
                filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                try:
                    filter_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                except ValueError:
                    filter_date = None
            if filter_date:
                queryset = queryset.filter(date_facture=filter_date)
        elif start_date_str and end_date_str:
            # Tenter de parser start_date
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                try:
                    start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
                except ValueError:
                    start_date = None
            # Tenter de parser end_date
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                try:
                    end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()
                except ValueError:
                    end_date = None
            if start_date and end_date:
                queryset = queryset.filter(date_facture__gte=start_date, date_facture__lte=end_date)
        elif year_str:
            # Filtrer par année
            try:
                year = int(year_str)
                queryset = queryset.filter(date_facture__year=year)
            except ValueError:
                pass
        
        # Vous pouvez ajouter d'autres filtres si nécessaire.
        return queryset.order_by('date_facture')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Récupérer les filtres pour les réafficher (optionnel)
        context['date'] = self.request.GET.get('date', '')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['year'] = self.request.GET.get('year', '')
        # Calculer les totaux pour les trois dernières colonnes
        aggregates = self.get_queryset().aggregate(
            sum_total_acte=Sum('total_acte'),
            sum_tiers_payant=Sum('tiers_payant'),
            sum_total_paye=Sum('total_paye')
        )
        context['sum_total_acte'] = aggregates['sum_total_acte'] or 0
        context['sum_tiers_payant'] = aggregates['sum_tiers_payant'] or 0
        context['sum_total_paye'] = aggregates['sum_total_paye'] or 0
        return context

# comptabilite/views.py

from django.shortcuts import render, redirect
from datetime import datetime, date
from django.db.models import Sum
from .models import Paiement

from django.shortcuts import render, redirect
from datetime import date
from django.db.models import Sum
from .models import Paiement

def cheque_listing(request):
    # POST : on coche tous les chèques non listés dont la date ≤ aujourd'hui
    if request.method == 'POST':
        Paiement.objects.filter(
            modalite_paiement="Chèque",
            date__lte=date.today(),
            liste=False
        ).update(liste=True)
        return redirect('cheque_listing')

    # GET : on n'affiche que ceux qui ne sont pas encore listés
    cheques = Paiement.objects.filter(
        modalite_paiement="Chèque",
        date__lte=date.today(),
        liste=False
    )
    count = cheques.count()
    total_montant = cheques.aggregate(total=Sum('montant'))['total'] or 0

    return render(request, 'comptabilite/cheque_listing.html', {
        'cheques': cheques,
        'count': count,
        'total_montant': total_montant,
        'filter_date': date.today().strftime("%d/%m/%Y"),
    })




from datetime import date, datetime
from django.shortcuts import render, redirect

def choix_date_cheques(request):
    """
    Permet de choisir la date pour la remise des chèques.
    Si l'utilisateur sélectionne "Aujourd'hui", on redirige avec la date du jour.
    Sinon, on utilise la date saisie.
    """
    if request.method == 'POST':
        option = request.POST.get('date_option')
        if option == 'today':
            chosen_date = date.today().strftime('%Y-%m-%d')
            return redirect(f"/facturation/cheques/?date={chosen_date}")
        elif option == 'other':
            other_date = request.POST.get('other_date')
            if other_date:
                # On s'assure que la date est valide ; ici, on suppose qu'elle est saisie en format ISO.
                try:
                    datetime.strptime(other_date, '%Y-%m-%d')
                    return redirect(f"/facturation/cheques/?date={other_date}")
                except ValueError:
                    # Si la date n'est pas au format attendu, on peut réafficher le formulaire avec une erreur.
                    context = {'error': "Format de date invalide. Veuillez utiliser le format AAAA-MM-JJ."}
                    return render(request, 'comptabilite/choix_date_cheques.html', context)
    return render(request, 'comptabilite/choix_date_cheques.html', {})


from django.forms.widgets import NumberInput

class IntegerNumberInput(NumberInput):
    def format_value(self, value):
        if value is None or value == '':
            return ''
        try:
            # Convertir en entier pour enlever les décimales.
            return str(int(round(float(value))))
        except (ValueError, TypeError):
            return super().format_value(value)

import pdfkit
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.conf import settings
from .models import Paiement
from django.utils import timezone
from django.template.loader import render_to_string

def remise_cheque(request):
    """
    Affiche la liste des paiements (chèques) non listés et à date <= aujourd'hui,
    puis, quand on valide (POST), marque 'listé' = True et renvoie le PDF.
    """
    today = timezone.localdate()

    # Si on vient de valider le formulaire (méthode POST)
    if request.method == 'POST':
        # Récupère tous les chèques encore non listés, date <= aujourd'hui
        cheques = Paiement.objects.filter(
            modalite_paiement='Chèque',
            date__lte=today,
            liste=False
        )
        # Marquer chacun comme listé
        cheques.update(liste=True)

        # Recalculer le contexte pour le PDF
        count = cheques.count()
        total = cheques.aggregate(total=models.Sum('montant'))['total'] or 0

        context = {
            'cheques': cheques,
            'count': count,
            'date_cheque': today.strftime('%d/%m/%Y'),
            'total_montant': total,
        }

        # Rendre le HTML du bordereau
        html = render_to_string('comptabilite/remise_cheque_pdf.html', context)

        # Générer le PDF
        pdf = pdfkit.from_string(html, False, options=settings.PDFKIT_OPTIONS)

        # Renvoyer le PDF au navigateur
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="remise_cheque_{today}.pdf"'
        return response

    # Sinon (GET), on affiche le listing et le bouton de validation
    cheques = Paiement.objects.filter(
        modalite_paiement='Chèque',
        date__lte=today,
        liste=False
    )
    count = cheques.count()
    total = cheques.aggregate(total=models.Sum('montant'))['total'] or 0

    return render(request, 'comptabilite/remise_cheque.html', {
        'cheques': cheques,
        'count': count,
        'date_cheque': today.strftime('%d/%m/%Y'),
        'total_montant': total,
    })

import io
from datetime import datetime, date
from django.db.models import Sum
from django.shortcuts import redirect
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from .models import Paiement

def print_cheque_listing(request):
    from datetime import datetime, date
    import io
    from django.db.models import Sum
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from .models import Paiement

    # 1. Récupération de la date
    d_str = request.GET.get('date')
    if d_str:
        try:
            filter_date = datetime.strptime(d_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                filter_date = datetime.strptime(d_str, '%d/%m/%Y').date()
            except ValueError:
                filter_date = date.today()
    else:
        filter_date = date.today()

    # 2. Requête initiale (liste=False)
    qs = Paiement.objects.filter(
        modalite_paiement="Chèque",
        date__lte=filter_date,
        liste=False
    ).order_by('date')

    # 3. On cashe en mémoire AVANT le .update()
    cheques = list(qs)
    if not cheques:
        # rien à lister → retour à la liste
        return redirect('cheque_listing')

    count = len(cheques)
    total_montant = sum(ch.montant for ch in cheques)

    # 4. On marque TOUTES ces lignes comme « listées »
    qs.update(liste=True)

    # 5. Construction du PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 2*cm
    c.setFont('Helvetica-Bold', 16)
    c.drawString(2*cm, y, "Dr. Florence FOURQUET | Dermatologie | Av. du Prince HINOI | Papeete")
    y -= 1*cm

    y = height - 2*cm
    c.setFont('Helvetica-Bold', 16)
    c.drawString(2*cm, y, "Av. du Prince HINOI | Papeete")
    y -= 1*cm

    c.setFont('Helvetica-Bold', 16)
    c.drawString(2*cm, y, f"Remise de {count} Chèqu(es)")
    y -= 1*cm

    c.setFont('Helvetica', 12)
    c.drawString(2*cm, y, f"Date de remise : {filter_date.strftime('%d/%m/%Y')}")
    y -= 1*cm

    # En‑tête du tableau
    c.setFont('Helvetica-Bold', 12)
    xs = [2*cm, 6*cm, 10*cm, 14*cm]
    for x, title in zip(xs, ["Date", "Banque", "Porteur", "Montant"]):
        c.drawString(x, y, title)
    y -= 0.7*cm

    # Lignes détaillées
    c.setFont('Helvetica', 11)
    for ch in cheques:
        if y < 2*cm:
            c.showPage()
            y = height - 2*cm
            # on ré‑affiche l’en‑tête
            c.setFont('Helvetica-Bold', 12)
            for x, title in zip(xs, ["Date", "Banque", "Porteur", "Montant"]):
                c.drawString(x, y, title)
            y -= 0.7*cm
            c.setFont('Helvetica', 11)

        c.drawString(xs[0], y, ch.date.strftime('%d/%m/%Y'))
        c.drawString(xs[1], y, ch.banque or "")
        c.drawString(xs[2], y, ch.porteur or "")
        c.drawRightString(xs[3] + 3*cm, y, f"{int(ch.montant)}")
        y -= 0.7*cm

    # Total en bas
    y -= 1*cm
    c.setFont('Helvetica-Bold', 12)
    c.drawString(2*cm, y, f"Nombre de chèque(s) : {count}   Total des montants : {int(total_montant)}")

    c.save()
    buffer.seek(0)

    # 6. Retour HTTP
    filename = f"remise_cheque_{filter_date.strftime('%Y%m%d')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import Facturation

def generate_numero(request, pk):
    """
    Génère et sauvegarde un numero_facture pour la Facturation pk
    si elle n'en a pas encore et que parcours_soin == False.
    """
    facture = get_object_or_404(Facturation.objects.select_related('code_acte'), pk=pk)
    code = facture.code_acte
    # seulement si pas déjà généré et hors parcours de soins
    if not facture.numero_facture and not (code and code.parcours_soin):
        now = timezone.localtime()
        facture.numero_facture = (
            f"FQ/{now.year}/{now.month:02d}/{now.day:02d}/"
            f"{now.hour:02d}:{now.minute:02d}"
        )
        facture.save(update_fields=['numero_facture'])
    return JsonResponse({'numero_facture': facture.numero_facture or ""})


